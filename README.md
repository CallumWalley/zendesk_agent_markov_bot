# zendesk_agent_markov_bot
Uses Zendesk API to generate markov chains for your amusement.

### Files
`construct_model.py`

`zendesk_credentials.json`

`default_inputs.json`

`corpus_cache/`

### Use


Call `construct_model.py` from command line, with the following optional keyword inputs:


* `make_cache` [bool] if false, will not save model.
* `use_cache` [bool] if false, will not use existing model ( of same specification ).
* `flavor` [string] Only use comments from user/s. Comma delimited, uses fuzzy search.
* `seed` [] Does nothing.
* `state_size` [int] State size for model. 1 will be nonsense. 4 will give results very similar to inputs.
* `max_build_period` [int] Number of days to go back in order to build model.
* `max_workers` [int] Max processes to use. Limiting factor is generally Zendesk rate limiting so don't put too high.
