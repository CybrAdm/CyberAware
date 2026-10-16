# AI use log

The incident rules, algorithm behavior, storage, cleaning, and analytics were written as separate member modules and then connected in this folder.

AI assistance was used to:

- Read the separate member files and the course requirement deck.
- Place the modules behind one Streamlit application: report, review, awareness, quiz, and dashboard.
- Split those modules into short files under core, algorithms, analytics, awareness, and auth.
- Add registration and an admin-only review and dashboard.
- Replace the incident-ID dictionary inside `IncidentIndex` with the hand-written hash table, and record Quick Sort comparisons, swaps, and recursive calls.
- Add the article and quiz seed content and the first-run simulated dataset call.

The member validation, status transitions, sort order, search results, queue order, and KPI formulas were not replaced with a new design.

Checked by running `python -m unittest -v test_member2_algorithms test_member4_data_analytics test_hash_table` after the connection, and by opening the Streamlit screens.
