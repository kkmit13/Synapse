Phase 1: Set up a basic strcture. Set up FastAPI server and get basic events and timestamps that are stored into a database using SQLite (one of the easiest ways to set up a DB). 

FASTAPI over Flask 

1. FASTAPI uses Async/Await, which helps with the multitasking of multiple devices at once
2. Has a built-in data checker for valid data unlike Flask (not built-in has to be added) using EventIn, rejects if datas not valid
3. Way easier to initialize server and DB beforehand and after


Set up a WebSocket server and initialized it. Set up a React frontend to show and display these timestamps and sensor logs. Test it out using fake logs to mimic a Raspberry Pi sending sensor data signals. Confirmed the server and DB functions and the websocket can take in the continuos flow of data

2 communication methods, Websocket and HTTP

HTTP - Post and Get (Sends events from devices into server and uses GET once on startup)
Websocket - Continually sends out data to be displayed on dashboard


Issue #1: It is difficult to read data logs due to constantly needing to scroll down
Solution: Set up a toggle feature with 3 different modes, AUTO, TOP, and OFF to choose display styling

Phase 1 pipeline:

Device utilizes HTTP Post -> sent to be timestamped (using Python function) and then stored in SQLite databse -> displayed on react dashboard using Websocket -> shown on screen


Phase 2: 

Create cleaner more readable UI and add multi-lane timeline to track events from mutlipe devices and sensors, so we can handle a larger workload while also keeping readability

App.js: Handles connections (Websocket) and is responsible for the recieving and sending of data (passes it to other JS files). Hold events list and loads history using GET /events on startup.

TimeLine.js: Displays events passed down from App.js, each device and sensor gets its lane (Horizontal Track) and event positioning is based on tsToPercent, seeing when events occur relative to each other
Also established the zoom (scroll and click), and the detail cards you get when clicking on the timeline markers

Feed.js: Displays events passed down from App.js vertically, so you can see each recent update, no seperated track/lane
Contains scroll mode logic (Auto/Top/Off)

DevicePanel.js: Provides status-cards for each device on the Feed panel (right side)
1. How many events sent per device
2. When it was last seen
3. Most recent event


Issue #1: Scrolling issue, scrolling down causes events to zoom out unintentially

Solution: Changed scroll wheel zoom to only work when holding cntrl. This also triggered pinch-to-zoom gesture adding an additional  way to zoom into timeline for a total of 3 options

Issue #2: Clicking on timestamps is difficult

Solution: Invisible 16px hitbox wrapped around each marker increasing hitbox while keeping it visually the same

Issue #3: The sensor data constantly switching around makes it hard to visually read each sensor data

Solution: Sorted lanes alphabetically so positions are fixed

Updated Flow: Device sends data using HTTP Post -> Event is then timestamped and stored in SQLite database  -> Websocket in Main.py send data -> Websocket living on App.js recieves data -> data is then stored in events list -> passed to TimeLine.js, DevicePanel.js, and Feed.js using props

Phase 3: 

What was done: 1 new python file added: AI.py
Main.py updated

New Frontend Files: AnomalyLog.js, AIPanel.js
Timeline.js updated

Now we have an AI chatbot, a red, orange, and cyan alert markers to the timeline which highlight severity and anomaly detected
We have notifications when not looking at Anomaly log
Anomaly log panel shows the full issue w/ fixes

2 main features:

Passive Anomaly detection:

In Main.py lives anomaly_scheduler, activating every 15 seconds (starts on server startup: asyncio.create_task(anomaly_scheduler()))

What anomaly_scheduler does: 
SQLite db rows are read out and converted into Python dictionaries using dict(row) (last 20 events, the timestamps/ids/sensor readings) using
recent = get_recent_events_from_db(limit=20) function call

These dictionaries are then looped through

Values are then extracted by key name, and these values are then put into an F-String to become plain text

This plain text is then sent to Haiku + other requests for the prompt

Haiku responds in JSON, only saying something if theres an anamoly, if not, it returns an empty array

That JSON string is then converted back to Python Dictionaries, 1 dictionary per anomaly

These anomaly dictionaries are then looped through to be timestamped, with an extra timestamp key being added to each one

Then each dictionary is appended to the anomaly_log list

Each anamoly dictionary is then automatically converted into JSON text (using send_json()), before being sent out via Main.py websocket to be recieved by App.js websocket

Once the message arrives, JSON.parse() is run to convert it into a JS object

App.js checks the type (either event or anomaly), and then puts it in either events list or anomalies list

And then if the Anomaly Panel is closed, a notification will appear on the top right

SetEvents adds the JS object into to the front of events list

Once SetEvents runs, all components using that list are updated, Feed, Timeline, Device Panel

React then re-renders each component with the new event

Events has a max of 500 events

The same thing goes w/ Anomalies, with a max of 50 events on display w/ events added to the end

AnomalyLog.js is affected
Timeline.js is affected




Frontend:
What each JS file does

Timeline.js: 
1. Recieves both the events list and anomalies list
2. Events are displayed as a line/marker on each horizontal lane
3. The anomaly lines show up as 3 different colors depending on severity (Red, Orange, Cyan)
4. Clicking the marker opens up a detail card showing the full event or anamoly info
5. You can zoom in multiple different ways
    a. Pinch zoom
    b. cntrl + scroll
    c. +/- buttons on screen
6. Lanes sorted alphabetically
7. Device/Sensor toggle switches between
    a. Showing 1 lane per device
    b. 1 lane per sensor

Feed.js:
1. Recieves events from events list
2. Each events is displayed on one vertical row, with the newest on top
3. Shows the timestamp, Device ID, event name, and value for each event
4. Has updated scroll mode logic (AUTO/TOP/OFF)

DevicePanel.js
1. Recieves events from events list (grouped by device)
2. Has a card for each device that is connected on the right
3. Each card shows: 
    a. How many events a device sent
    b. When it was last seen
    c. The most recent event



AnomalyLog.js
1. Recieved anomalies from anomalies list
2. Panel that can be toggled showing full anamoly history with most recent on top
3. Each card shows:
    a. Severity
    b. Device
    c. Sensor
    d. detection time
    e. an AI explanation of what went wrong
    f. And a suggested fix
4. App.js Loads the existing anomalies on startup (used GET /anomalies)

AIPanel.js how it works:

 On clicking the enter key, sendMessage() is run

 Message then gets added to the message list, to be shown on screen (same way all the other things are rendered)

 Typing animation added

 HTTP Post sends message as JSON text to a /chat endpoint

Once that is sent, 3 things happen:
    1. Last 100 events taken from SQLite (converted to dictionaries which is looped through)
    2. anomaly_log is also passed in directly
    3. Calles ai.chat() function from ai.py

In ai.chat(), it formats the 100 events into plain text (same as how they did it in anomaly detection in an f-string)

The anomaly log is also the converted into plain text, taking the last 10 anomalies into a short summary, same method, looping through them into F-strings

All of this info is then packaged into the prompt w/ the users questions

This prompt is then sent to Haiku through Anthropic API w/ max_tokens=500 keeping the response short and sweet

It then takes Haikus repsonse object and returns it back as a plain string to main.py

In main.py, it converts the response to a dictionary, and then sends it back to AIPanel.js as JSON, completing the HTTP post request

res.json() function then converts the JSON string back into a JS object, data.response pulls out the text string and that gets added to messages list, react re-renders then and it appears in chat

Chat has 2 roles: ai, and user

Chat window loops through these dictionaries and each gets rendered differently based on role

There is also a full screen feature



















IN-DEPTH FLOW:

Device sends data using HTTP Post as JSON -> This data is then checked using EventIn Model to make sure the data it valid -> This JSON is then converted into a Python Dictionary using .model_dump() -> A new timestamp key is added to the dictionary -> individual values extracted from dictionary -> each value is then stored in column in the SQLite database -> Data being sent out is then converted back into a dictionary and then to JSON -> Websocket in Main.py send data -> Websocket living on App.js recieves data (connection was opened since startup) -> data is then stored in events list -> passed to TimeLine.js, DevicePanel.js, and Feed.js using props