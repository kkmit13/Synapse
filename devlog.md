Phase 1: Set up a basic working pipeline. Set up FastAPI server and get basic events and timestamps that are stored into a database using SQLite (one of the easiest ways to set up a DB). 

FASTAPI over Flask 

1. FASTAPI uses Async/Await, allowing multitasking with multiple devices at once, Flask can only handle one at a time
2. Checks for valid data unlike Flask using EventIn, rejects if datas not valid
3. Way easier to initialize server and DB beforehand and after



Set up a WebSocket server and initialized it. Set up a React frontend to show and display these timestamps and sensor logs. Test it out using fake logs to mimic a Raspberry Pi sending sensor data signals. Confirmed the server database functions and the websocket can continually take in data correctly

2 communication methods, Websocket and HTTP

HTTP - Post and Get (Sends events from devices into server and uses GET once on startup)
Websocket - Continually sends out data to be displayed on dashboard


Issue #1: It is difficult to read data logs due to constantly needing to scroll down
Solution: Set up a toggle feature with 3 different modes, AUTO, TOP, and OFF to choose display styling

Phase 1 pipeline:

Device utilizes HTTP Post -> sent to be timestamped (using Python function) and then stored in SQLite databse -> displayed on react dashboard using Websocket -> shown on screen


Phase 2: Create a cleaner more 