import json, contextlib, io, dataclasses
from gim.historical_backtest import run_historical_backtest
with contextlib.redirect_stdout(io.StringIO()):
    r=run_historical_backtest()
d=dataclasses.asdict(r)
print("NEW GOLDEN: gdp=%.4f co2=%.4f temp=%.4f bias=%.4f"%(
    d['gdp_rmse_trillions'],d['global_co2_rmse_gtco2'],d['temperature_rmse_c'],d['temperature_bias_c']))
# write baseline fixture in same key order as before
with open('tests/fixtures/historical_backtest_baseline.json','w') as fh:
    json.dump(d,fh,indent=2); fh.write('\n')
print("baseline regenerated")
