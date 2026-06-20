import contextlib, io, itertools
from gim.climate_backtest import run_climate_backtest, load_observations, load_emissions_history
from gim.historical_backtest import run_historical_backtest
obs=load_observations(); hist=load_emissions_history()
def long_rmse(ov): return run_climate_backtest(obs,mode="concentration",params_override=ov,emissions_history=hist).scores["temperature_rmse"]
def econ(ov):
    with contextlib.redirect_stdout(io.StringIO()):
        r=run_historical_backtest(params_override=ov)
    return r.temperature_rmse_c, r.temperature_bias_c
best=None
print(f"{'ECS':>4} {'cap':>4} {'oex':>4} | {'long':>6} | {'econ':>6} {'bias':>7}")
for ecs,cap,oex in itertools.product([2.8,3.0,3.2],[7.0,8.0,9.0],[0.9,1.0,1.1]):
    ov={'ECS_DEFAULT':ecs,'HEAT_CAP_SURFACE':cap,'OCEAN_EXCHANGE':oex}
    lr=long_rmse(ov); er,eb=econ(ov)
    feas= er<0.15 and abs(eb)<0.02
    if feas:
        score=lr
        if best is None or score<best[0]: best=(score,ecs,cap,oex,er,eb)
    print(f"{ecs:4.1f} {cap:4.0f} {oex:4.1f} | {lr:6.3f} | {er:6.3f} {eb:7.3f} | {'YES' if feas else ''}")
print('\nBEST FEASIBLE (min long s.t. gates): long=%.3f ECS=%.1f cap=%.0f oex=%.1f econ=%.3f bias=%.3f'%best)
