# csv_reader
A tool create plots from your datalogs

![a graph](.github/images/plotwindow.png)

***
## Features
- Takes the .csv of your datalog and extracts data for each pull
- Allows you to plot parameters of your choice vs time for each pull and export said figures

## Instructions
1. Select a datalog file using the button on the start tab.
2. Input the parameters, or use default, to identify pulls in your log and hit start.
3. Note: The 'throttle threshold' parameter identifies a pull when your throttle is >= the value.
4. The time filter parameter omits pulls whose duration is <= the value, for filtering out erroneous throttle spikes.
5. After hitting start, head to the Graph tab. There you will see a dropdown for each pull in your log.
6. Hit the 'plot' button and a new window will open for your pull.
7. Then, select which parameters you wish to plot on the left. Note that at this time only two can be plotted at a time.
8. If you wish to export your figure, you can do so with the save button.
***
## Building from Source
To run the app from source you will need the following dependencies:
- Python 3 (built using 3.10, earlier versions will probably work fine)
- matplotlib
- pandas
- qtpy
- PyQt5

**Note:**
To compile the app to .exe you will need a developer build of pyinstaller. I used 5.0 but version 4 will probably work fine. The current version 3 release does not work with matplotlib.
