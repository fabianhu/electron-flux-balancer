#!/bin/bash

current_date=$(date +%Y-%m-%d_%H-%M-%S)

# Check if the "efb_main.py" process is running
if pgrep -f "efb_main.py" > /dev/null; then
  # "process is running."
  :
else
  echo "${current_date}: process not found."
  cp "out.txt" "out_${current_date}.txt"
  /usr/bin/nohup /usr/bin/python3 /home/pi/efb_main.py >/home/pi/out.txt 2>&1 &
fi

