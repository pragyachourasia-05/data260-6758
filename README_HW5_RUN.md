# HW5 PyCharm run guide

Open the existing `Assignment_1` repository in PyCharm and copy these files into the matching relative folders. Do not create a second repository.

1. Activate the existing virtual environment and install `pip install "mcp[cli]" httpx`.
2. Run `python backend/retry_fault_benchmark.py` from the repository root. It creates `reports/hw05/raw/fault_injection_results.json`.
3. Run `python backend/offline_tests.py`. The required screenshot should show every `PASS` line and the final `SUMMARY: 8/8 PASS`.
4. Run `mcp dev backend/app/meals_server.py`; test the four tools in Inspector and save one screenshot per tool.
5. Run `mcp dev backend/app/domain_mcp_server.py`; test each of the three tools once successfully and once with invalid input.
6. Run the existing FastAPI backend on port 8458, then run `python verify_hw05.py` and save the generated `reports/hw05/verification.json`.
7. Fill the metrics table and real timestamps, add your screenshots to the report, commit, and tag the final state `hw5`.

The Redux slice is a replacement for the existing HW4 data layer. In `frontend/src/main.jsx`, wrap the app with `<Provider store={store}>`, and import the store from `./store/store`. Use `useSelector((state) => state.listings)` and dispatch the four thunks from the existing Home/Create/Update/Delete pages.
