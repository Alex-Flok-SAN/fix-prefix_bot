# scripts/run_fpf_backtest_eth.py
import argparse, pandas as pd, numpy as np, bisect, json
from pathlib import Path

def nearest(levels, price):
    i = bisect.bisect_left(levels, price); c=[]
    if i<len(levels): c.append(levels[i])
    if i>0: c.append(levels[i-1])
    if not c: return None
    return c[int(np.argmin([abs(price-x) for x in c]))]

def load_csvs(dirpath, pattern):
    p = Path(dirpath)
    dfs = []
    files = sorted(p.glob(pattern))
    if not files:
        raise SystemExit(f"No CSVs match pattern '{pattern}' in {dirpath}")
    for f in files:
        dfs.append(pd.read_csv(f))
    df = pd.concat(dfs, ignore_index=True).sort_values("ts_open_ms")
    df["ts"] = pd.to_datetime(df["ts_open_ms"], unit="ms", utc=True)
    return df

def detect_and_score(df_all):
    df=df_all.set_index("ts").sort_index().copy()
    df["range"]=df["high"]-df["low"]
    df["body"]=(df["close"]-df["open"]).abs()
    df["wick_upper"]=df["high"]-df[["open","close"]].max(axis=1)
    df["wick_lower"]=df[["open","close"]].min(axis=1)-df["low"]
    safe=lambda a,b:(a/b).replace([np.inf,-np.inf],np.nan).fillna(0)
    df["wur"]=safe(df["wick_upper"],df["range"])
    df["wlr"]=safe(df["wick_lower"],df["range"])
    df["br"]=safe(df["body"],df["range"])
    df["atr1"]=df["range"].rolling(14,min_periods=5).mean()
    df["r20"]=df["range"].rolling(20,min_periods=5).mean()
    df["typ"] = df[["high","low","close"]].mean(axis=1)
    df["tpv"] = df["typ"]*df["volume"]

    daily=df.resample("1D")
    HOD=daily["high"].max().dropna()
    LOD=daily["low"].min().dropna()
    VWAP=(daily["tpv"].sum()/daily["volume"].sum().replace(0,np.nan)).dropna()

    pmin,pmax=float(df["low"].min()), float(df["high"].max())
    r5=list(np.arange(np.floor(pmin/5)*5,   np.ceil(pmax/5)*5+1e-9,   5.0))
    r10=list(np.arange(np.floor(pmin/10)*10, np.ceil(pmax/10)*10+1e-9,10.0))
    r50=list(np.arange(np.floor(pmin/50)*50, np.ceil(pmax/50)*50+1e-9,50.0))
    ROUNDS=sorted(set(r5+r10+r50))

    hi=df["high"]; lo=df["low"]
    sh=(hi.shift(0)>hi.shift(1))&(hi.shift(0)>hi.shift(2))&(hi.shift(0)>hi.shift(-1))&(hi.shift(0)>hi.shift(-2))
    sl=(lo.shift(0)<lo.shift(1))&(lo.shift(0)<lo.shift(2))&(lo.shift(0)<lo.shift(-1))&(lo.shift(0)<lo.shift(-2))
    SH=sorted(df[sh]["high"].astype(float).tolist())
    SL=sorted(df[sl]["low"].astype(float).tolist())

    eps=0.0005; k_w=0.6; k_r=1.3; dmin_mult=0.5
    rows=df.reset_index()
    sig=[]
    for i in range(2,len(rows)-2):
        r=rows.iloc[i]
        if pd.isna(r["atr1"]): continue
        day=r["ts"].normalize()
        Ls=[]
        if day in HOD.index: Ls.append(("HOD", float(HOD.loc[day])))
        if day in LOD.index: Ls.append(("LOD", float(LOD.loc[day])))
        if day in VWAP.index: Ls.append(("VWAP", float(VWAP.loc[day])))
        Lr=nearest(ROUNDS, float(r["close"]))
        if Lr is not None: Ls.append(("ROUND", float(Lr)))
        Lsh=nearest(SH, float(r["close"])); Lsl=nearest(SL, float(r["close"]))
        if Lsh is not None: Ls.append(("SWING_H", float(Lsh)))
        if Lsl is not None: Ls.append(("SWING_L", float(Lsl)))
        if not Ls: continue

        high,low,op,cl=float(r["high"]),float(r["low"]),float(r["open"]),float(r["close"])
        wlr,wur=float(r["wlr"]),float(r["wur"])
        r20=float(r["r20"]) if not np.isnan(r["r20"]) else float(r["range"])
        atr1=float(r["atr1"])

        picked=None
        for lt,L in Ls:
            mult=0.5 if lt in ("SWING_H","SWING_L") else 1.0
            et=L*eps*mult
            touch_long=(low<=L+et) and (cl>=L-et)
            touch_short=(high>=L-et) and (cl<=L+et)
            condL=touch_long and (wlr>=k_w) and (cl>op)
            condS=touch_short and (wur>=k_w) and (cl<op)
            if not (condL or condS): continue
            r_fix=rows.iloc[i+1]
            small=(float(r_fix["br"])<=0.35)
            closeL=float(r_fix["close"])>=max(op,cl)
            closeS=float(r_fix["close"])<=min(op,cl)
            if condL and not (small and closeL): continue
            if condS and not (small and closeS): continue
            r_imp=rows.iloc[i+2]
            big=float(r_imp["range"])>=k_r*r20
            dmin=max(dmin_mult*atr1,0.0)
            awayL=float(r_imp["low"])>L+dmin
            awayS=float(r_imp["high"])<L-dmin
            if condL and not (big and awayL): continue
            if condS and not (big and awayS): continue
            picked={"ts_prefix":r["ts"],"ts_fix":rows.iloc[i+1]["ts"],"ts_impulse":rows.iloc[i+2]["ts"],
                    "level_type":lt,"L":L,"direction":"long" if condL else "short",
                    "prefix_low":low,"prefix_high":high,"fix_close":float(r_fix["close"])}
            break
        if picked: sig.append(picked)
    return pd.DataFrame(sig), df_all

def outcomes(sig_df, df_all):
    if sig_df.empty:
        return sig_df.assign(status=[]), {"n_signals":0, "outcomes":{}, "winrate_TP1plus_%":0.0, "winrate_TP2_%":0.0}
    idx=df_all.set_index(pd.to_datetime(df_all["ts_open_ms"], unit="ms", utc=True)).sort_index()
    out=[]
    for _,s in sig_df.iterrows():
        entry_time=pd.Timestamp(s["ts_fix"]); start=idx.index.get_indexer([entry_time], method="nearest")[0]
        entry=float(s["fix_close"])
        if s["direction"]=="long":
            sl=float(s["prefix_low"])-0.05; R=entry-sl; tp1=entry+R; tp2=entry+2*R
        else:
            sl=float(s["prefix_high"])+0.05; R=sl-entry; tp1=entry-R; tp2=entry-2*R
        highs=idx["high"].iloc[start+1:start+1+360]; lows=idx["low"].iloc[start+1:start+1+360]
        hit_tp1=hit_tp2=hit_sl=None; mae=0.0; mfe=0.0
        for t,h,l in zip(highs.index, highs.values, lows.values):
            if s["direction"]=="long":
                mfe=max(mfe,(h-entry)/R); mae=min(mae,(l-entry)/R)
                if l<=sl: hit_sl=t; break
                if h>=tp2: hit_tp2=t; break
                if h>=tp1 and hit_tp1 is None: hit_tp1=t
            else:
                mfe=max(mfe,(entry-l)/R); mae=min(mae,(entry-h)/R)
                if h>=sl: hit_sl=t; break
                if l<=tp2: hit_tp2=t; break
                if l<=tp1 and hit_tp1 is None: hit_tp1=t
        status="timeout"
        if hit_sl is not None: status="SL"
        elif hit_tp2 is not None: status="TP2"
        elif hit_tp1 is not None: status="TP1"
        out.append({"status":status,"mfe_R":round(mfe,3),"mae_R":round(mae,3)})
    odf=pd.concat([sig_df.reset_index(drop=True), pd.DataFrame(out)], axis=1)
    wr1=float((odf["status"].isin(["TP1","TP2"]).mean()*100.0)) if len(odf) else 0.0
    wr2=float((odf["status"].eq("TP2").mean()*100.0)) if len(odf) else 0.0
    by_level = odf.groupby("level_type")["status"].value_counts().unstack(fill_value=0).to_dict()
    return odf, {"n_signals":int(len(odf)),
                 "outcomes":odf["status"].value_counts().to_dict(),
                 "winrate_TP1plus_%":round(wr1,2),
                 "winrate_TP2_%":round(wr2,2),
                 "by_level": by_level}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/history/ETHUSDT", help="Directory with CSV files")
    ap.add_argument("--symbol", default="ETHUSDT", help="Symbol (used for defaults)")
    ap.add_argument("--pattern", default=None, help="Glob pattern for CSVs inside --dir; default: {SYMBOL}_M1_*.csv")
    ap.add_argument("--out-signals", default=None, help="Path to save detected setups CSV")
    ap.add_argument("--out-outcomes", default=None, help="Path to save outcomes CSV")
    args=ap.parse_args()

    pattern = args.pattern or f"{args.symbol}_M1_*.csv"
    df_all = load_csvs(args.dir, pattern)
    sig_df, _ = detect_and_score(df_all)
    odf, summary = outcomes(sig_df, df_all)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # defaults for outputs if not provided
    if args.out_signals is None:
        args.out_signals = str(Path(args.dir) / f"{args.symbol}_FPF_signals.csv")
    if args.out_outcomes is None:
        args.out_outcomes = str(Path(args.dir) / f"{args.symbol}_FPF_outcomes.csv")

    Path(args.out_signals).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_outcomes).parent.mkdir(parents=True, exist_ok=True)

    sig_df.to_csv(args.out_signals, index=False)
    odf.to_csv(args.out_outcomes, index=False)
    print(f"[saved] signals -> {args.out_signals}")
    print(f"[saved] outcomes -> {args.out_outcomes}")