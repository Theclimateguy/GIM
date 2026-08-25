# Public release

Built by `scripts/build_public_release.py` from the working repository.

Russia is modelled here as a single consolidated country agent, identically to the other 56 -- which is the model the paper describes. The working repository also carries an intra-country block layer and a sub-national decomposition of Russia; neither is part of this release, of the paper, or of any result reported in it.

This is not a subset of the published model: the block layer is opt-in (`BLOCK_LAYER_AGENTS`, empty by default) and every number in the paper is produced with it inactive. The build verifies that by running the historical backtest in this tree and requiring it to match the working repository exactly on the GDP, CO2, temperature and resource-price RMSEs and on all 20 country-level GDP RMSEs.
