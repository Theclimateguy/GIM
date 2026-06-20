import contextlib, io, itertools
from gim.climate_backtest import run_climate_backtest, load_observations, load_emissions_history
from gim.historical_backtest import run_historical_backtest

obs=load_observations(); hist=load_emissions_history()

def long_rmse(ov):
    return run_climate_backtest(obs,mode="concentration",params_override=ov,emissions_history=hist).scores["temperature_rmse"]

def econ(ov):
    with contextlib.redirect_stdout(io.StringIO()):
        r=run_historical_backtest(params_override=ov)
    return r.temperature_rmse_c, r.temperature_bias_c

ECS=[2.5,3.0,3.5]
CAP=[8.0,12.0,18.0]
OEX=[0.7,1.0]
print(f"{'ECS':>4} {'cap':>4} {'oex':>4} | {'long':>6} | {'econ':>6} {'bias':>7} | feasible(econ<0.15,|bias|<0.02)")
rows=[]
for ecs,cap,oex in itertools.product(ECS,CAP,OEX):
    ov={'ECS_DEFAULT':ecs,'HEAT_CAP_SURFACE':cap,'OCEAN_EXCHANGE':oex}
    lr=long_rmse(ov); er,eb=econ(ov)
    feas = er<0.15 and abs(eb)<0.02
    rows.append((lr,ecs,cap,oex,er,eb,feas))
    print(f"{ecs:4.1f} {cap:4.0f} {oex:4.1f} | {lr:6.3f} | {er:6.3f} {eb:7.3f} | {'YES' if feas else ''}")
feas=[r for r in rows if r[6]]
if feas:
    b=min(feas,key=lambda r:r[0])
    print('\nBEST FEASIBLE: long=%.3f ECS=%.1f cap=%.0f oex=%.1f econ=%.3f bias=%.3f'%(b[0],b[1],b[2],b[3],b[4],b[5]))
else:
    print('\nNo feasible point in grid.')
