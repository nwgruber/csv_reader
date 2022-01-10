import sys
import matplotlib
matplotlib.use('Qt5Agg')
import pandas as pd
from qtpy.QtCore import Qt, QSettings
from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
        QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSizePolicy, QScrollArea, QTabWidget, QToolTip, QVBoxLayout, QWidget)
#import pyqtgraph as pg
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from lib import read_datalog, get_pulls, get_pull_info

class MultiPlotFigure(FigureCanvasQTAgg):
    def __init__(self, title = '', parent = None):
        fig = Figure()
        self.title = title
        self.axes = fig.add_subplot(111)
        self.axes2 = self.axes.twinx()
        self.axes_refs = [self.axes, self.axes2]
        super(MultiPlotFigure, self).__init__(fig)
        self.axes.set_xlabel('Time (sec)')
        if bool(title):
            self.axes.set_title(title)
        fig.tight_layout(pad = 3)
        self._plot_refs = [None, None]
        self.colors = ['b', 'r']

    def plot_index(self, xdata, ydata, fig_num, y_text = '', legend_text = ''):
        current_ax = self.axes_refs[fig_num]
        if self._plot_refs[fig_num] is None:
            self._plot_refs[fig_num] = current_ax.plot(xdata, ydata, self.colors[fig_num])[0]
        else:
            self._plot_refs[fig_num].set_ydata(ydata)
        if bool(y_text):
            current_ax.set_ylabel(y_text)
        if bool(legend_text):
            self._plot_refs[fig_num].set_label(legend_text)
            lines1, labels1 = self.axes.get_legend_handles_labels()
            lines2, labels2 = self.axes2.get_legend_handles_labels()
            self.axes.legend(lines1 + lines2, labels1 + labels2, loc = 0)
        self.draw()

    def clear_plot(self, fig_num):
        if fig_num != -1:
            # Clear one plot
            self.axes_refs[fig_num].cla()
            self._plot_refs[fig_num] = None
        else:
            # Clear all plots
            for i in range(2):
                self.axes_refs[i].cla()
                self._plot_refs[i] = None
        self.axes.set_xlabel('Time (sec)')
        if bool(self.title):
            self.axes.set_title(self.title)
        self.draw()

class DoubleLineEdit(QLineEdit):
    def __init__(self, lower, upper, decimals, parent = None):
        super(DoubleLineEdit, self).__init__(parent)
        self.double_validator = QDoubleValidator(lower, upper, decimals)
        self.setValidator(self.double_validator)

    def validate_input(self):
        if self.text() != '':
            value = float(self.text())
            lower = self.double_validator.bottom()
            if lower.is_integer():
                lower = int(lower)
            upper = self.double_validator.top()
            if upper.is_integer():
                upper = int(upper)

            if value > upper:
                self.setText(str(upper))
            elif value < lower:
                self.setText(str(lower))

    def value(self):
        return float(self.text())

class ErrorMsg(QMessageBox):
    def __init__(self, msgtext, infotext = '', parent = None):
        super(ErrorMsg, self).__init__(parent)
        self.setIcon(QMessageBox.Critical)
        self.setWindowTitle('Error')
        self.setText(msgtext)
        if bool(infotext):
            self.setInformativeText(infotext)
        self.setStandardButtons(QMessageBox.Ok)

class PullPlot(QDialog):
    def __init__(self, df: pd.DataFrame, fig_title, parent = None):
        super(PullPlot, self).__init__(parent)
        self.fig_title = fig_title
        self.setWindowTitle(fig_title)
        self.x_values = df['Time (sec)']
        self.df = df.drop('Time (sec)', axis = 1)
        #print(self.df)
        col_names = {}
        for col in self.df.columns:
            unit_start = col.index('(')
            col_names[col] = {
                'name': col[:(unit_start - 1)],
                'unit': col[unit_start:].strip('()')
            }
        self.col_names = col_names
        self.active_plots = [None, None]
        self.createMainLayout()

    def createMainLayout(self):
        mainLayout = QHBoxLayout()
        leftLayout = QGroupBox('Curves')
        leftLayout.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        leftWrapLayout = QVBoxLayout()
        leftScrollBoxLayout = QVBoxLayout()
        leftScrollBox = QScrollArea()
        scrollContent = QWidget()

        self.colCheckBoxes = [QCheckBox(col) for col in self.col_names.keys()]
        [x.stateChanged.connect(self.curveCheckBoxChanged) for x in self.colCheckBoxes]
        [leftScrollBoxLayout.addWidget(x) for x in self.colCheckBoxes]

        scrollContent.setLayout(leftScrollBoxLayout)
        leftScrollBox.setWidget(scrollContent)
        leftWrapLayout.addWidget(leftScrollBox)

        leftLayout.setLayout(leftWrapLayout)

        rightWidget = QWidget()
        rightLayout = QVBoxLayout()
        self.plotWidget = MultiPlotFigure(title = self.fig_title)
        toolbar = NavigationToolbar(self.plotWidget, self)
        unwanted_btns = ['Subplots']
        for x in toolbar.actions():
            if x.text() in unwanted_btns:
                toolbar.removeAction(x)
        rightLayout.addWidget(toolbar)
        rightLayout.addWidget(self.plotWidget)
        rightWidget.setLayout(rightLayout)

        mainLayout.addWidget(leftLayout)
        mainLayout.addWidget(rightWidget)
        self.setLayout(mainLayout)

    def curveCheckBoxChanged(self):
        current_widget = self.sender()
        requested_plot = current_widget.text()
        widget_states = [x.isChecked() for x in self.colCheckBoxes]
        if widget_states.count(True) > 1:
            # Two boxes checked, disable others
            [x.setDisabled(True) for x in self.colCheckBoxes if not x.isChecked()]
        else:
            # Enable all checkboxes
            [x.setDisabled(False) for x in self.colCheckBoxes]
        last_plots = self.active_plots
        requested_plots = [x for x in self.colCheckBoxes if x.isChecked()]
        if len(requested_plots) == 0:
            # Removing all plots
            self.plotWidget.clear_plot(-1)
            self.active_plots = [None, None]
        elif len(requested_plots) > len(list(filter(bool, last_plots))):
            # Add an additional plot
            plot_index = last_plots.index(None)
            self.active_plots[plot_index] = requested_plot
            self.plotWidget.plot_index(self.x_values, self.df[requested_plot], plot_index, y_text = requested_plot, legend_text = self.col_names[requested_plot]['name'])
        else:
            # Removing a plot
            plot_index = last_plots.index(requested_plot)
            self.active_plots[plot_index] = None
            if plot_index == 0:
                self.active_plots = [self.active_plots[1], None]
            remaining_plot = self.active_plots[0]
            self.plotWidget.clear_plot(-1)
            self.plotWidget.plot_index(self.x_values, self.df[remaining_plot], 0, y_text = remaining_plot, legend_text = self.col_names[remaining_plot]['name'])

class WidgetGallery(QWidget):
    def __init__(self, parent = None):
        super(WidgetGallery, self).__init__(parent)
        self.createMainLayout()
        self.presscount = 0
        self.datalogfile = ''
        self.settings = QSettings('nwgruber', 'Datalog Reader')
        if self.settings.contains('last_log_dir'):
            self.last_log_dir = self.settings.value('last_log_dir')
        else:
            self.last_log_dir = ''

    def createMainLayout(self):
        mainLayout = QVBoxLayout()
        self.mainWidget = QTabWidget()

        self.createStartTab()
        mainLayout.addWidget(self.mainWidget)
        self.setLayout(mainLayout)

    def createStartTab(self):
        startTab = QWidget()
        self.startTabLayout = QVBoxLayout()
        # Start box
        startBox = QGroupBox('File')
        startBoxLayout = QVBoxLayout()
        self.fileLabel = QLabel('No file selected')
        self.fileBtn = QPushButton('Select a Datalog')
        self.fileLabel.setBuddy(self.fileBtn)

        self.fileBtn.clicked.connect(self.fileBtnPressed)

        startBoxLayout.addWidget(self.fileLabel)
        startBoxLayout.addWidget(self.fileBtn)
        startBox.setLayout(startBoxLayout)
        # Options box
        optsBox = QGroupBox('Options')
        optsBoxLayout = QFormLayout()

        self.throttleInput = DoubleLineEdit(1.0, 100.0, 2)
        self.throttleInput.setToolTip('Omit data when throttle is below this number')
        self.throttleInput.setText('50')

        self.timeFilterInput = DoubleLineEdit(0.001, 10.0, 3)
        self.timeFilterInput.setToolTip('Omit pulls whose duration is less than this number')
        self.timeFilterInput.setText('0.5')

        self.startBtn = QPushButton('Start')
        self.startBtn.clicked.connect(self.startBtnPressed)

        self.optsBoxDisabled(True)
        optsBoxLayout.addRow('Throttle Threshold:', self.throttleInput)
        optsBoxLayout.addRow('Time Filter:', self.timeFilterInput)
        optsBoxLayout.addRow(self.startBtn)
        optsBox.setLayout(optsBoxLayout)

        self.startTabLayout.addWidget(startBox)
        self.startTabLayout.addWidget(optsBox)
        startTab.setLayout(self.startTabLayout)

        self.mainWidget.addTab(startTab, 'Start')

    def fileBtnPressed(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setNameFilter('Datalogs (*.csv)')
        if bool(self.last_log_dir):
            dialog.setDirectory(self.last_log_dir)

        if dialog.exec_():
            self.datalogfile = dialog.selectedFiles()[0]
            self.fileLabel.setText('File: ' + self.datalogfile.rpartition('/')[2])
            self.settings.setValue('last_log_dir', self.datalogfile.rpartition('/')[0])
            self.optsBoxDisabled(False)

    def startBtnPressed(self):
        [self.datalog, self.ap_info] = read_datalog(self.datalogfile)
        self.throttleInput.validate_input()
        self.timeFilterInput.validate_input()
        # Get pulls
        self.pulls = get_pulls(self.datalog, self.throttleInput.value(), self.timeFilterInput.value())
        if bool(self.pulls):
            # create second tab
            self.pull_info = get_pull_info(self.pulls)
            if self.mainWidget.count() == 1:
                self.createGraphTab()
            else:
                self.updateGraphTab()
            self.mainWidget.setCurrentIndex(1)
        else:
            msg = ErrorMsg('No pulls found in datalog.', infotext = 'Your throttle threshold is too low or time filter too high.')
            msg.exec_()


    def optsBoxDisabled(self, disabled):
        self.throttleInput.setDisabled(disabled)
        self.timeFilterInput.setDisabled(disabled)
        self.startBtn.setDisabled(disabled)

    def createGraphTab(self):
        self.graphTab = QWidget()
        graphTabLayout = QVBoxLayout()
        graphTabBox = QGroupBox('Create Plot')
        graphTabBoxLayout = QFormLayout()

        self.pullPicker = QComboBox()
        self.pullStartLabel = QLabel()
        self.pullDurationLabel = QLabel()
        self.plotBtn = QPushButton('Plot')
        self.plotBtn.clicked.connect(self.plotBtnPressed)
        self.updateGraphTab()
        self.pullPicker.activated.connect(self.pullPickerChanged)

        graphTabBoxLayout.addRow('Pull:', self.pullPicker)
        graphTabBoxLayout.addRow(self.pullStartLabel)
        graphTabBoxLayout.addRow(self.pullDurationLabel)
        graphTabBoxLayout.addRow(self.plotBtn)
        graphTabBox.setLayout(graphTabBoxLayout)
        graphTabLayout.addWidget(graphTabBox)
        self.graphTab.setLayout(graphTabLayout)
        self.mainWidget.addTab(self.graphTab, 'Graph')

    def updateGraphTab(self):
        formspec = '{:<.2f}'
        pullPickerItems = [str(x) for x in self.pull_info.keys()]
        self.pullPicker.clear()
        self.pullPicker.addItems(pullPickerItems)
        start = formspec.format(self.pull_info[1]['start'])
        duration = formspec.format(self.pull_info[1]['duration'])
        self.pullStartLabel.setText(f'Start: {start} sec')
        self.pullDurationLabel.setText(f'Duration: {duration} sec')

    def pullPickerChanged(self):
        formspec = '{:<.2f}'
        i = self.pullPicker.currentIndex()
        selected_pull = self.pull_info[i + 1]
        start = formspec.format(selected_pull['start'])
        duration = formspec.format(selected_pull['duration'])
        self.pullStartLabel.setText(f'Start: {start} sec')
        self.pullDurationLabel.setText(f'Duration: {duration} sec')

    def plotBtnPressed(self):
        selected_pull = self.pullPicker.currentIndex()
        pull_df = self.pulls[selected_pull]
        fig_title = 'Pull ' + str(selected_pull + 1)
        testplot = PullPlot(pull_df, fig_title)
        testplot.exec_()

def main():
    app = QApplication([])
    app.setStyle('Fusion')
    window = WidgetGallery()
    window.setWindowTitle('Datalog Plotter')
    window.show()
    app.exec()

if __name__ == '__main__':
    main()
