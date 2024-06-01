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
        super().__init__(fig)
        self.axes.set_xlabel('Time (sec)')
        if bool(title):
            self.axes.set_title(title)
        fig.tight_layout(pad = 3)
        self._plot_refs = [None, None]
        self.colors = ['b', 'r']

    def plot_index(self, xdata: pd.Series, ydata: pd.Series, fig_num: int, y_text: str = '', legend_text: str = ''):
        current_ax = self.axes_refs[fig_num]
        if self._plot_refs[fig_num] is None:
            self._plot_refs[fig_num] = current_ax.plot(xdata.values, ydata.values, self.colors[fig_num])[0]
        else:
            self._plot_refs[fig_num].set_ydata(ydata.values)
        if bool(y_text):
            current_ax.set_ylabel(y_text)
        if bool(legend_text):
            self._plot_refs[fig_num].set_label(legend_text)
            lines1, labels1 = self.axes.get_legend_handles_labels()
            lines2, labels2 = self.axes2.get_legend_handles_labels()
            self.axes.legend(lines1 + lines2, labels1 + labels2, loc=0)
        self.draw()

    def clear_plot(self, fig_num: int):
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
    def __init__(self, lower: float, upper: float, decimals: int, parent=None):
        super().__init__(parent)
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
    def __init__(self, msgtext: str, infotext: str = '', parent=None):
        super().__init__(parent)
        self.setIcon(QMessageBox.Critical)
        self.setWindowTitle('Error')
        self.setText(msgtext)
        if bool(infotext):
            self.setInformativeText(infotext)
        self.setStandardButtons(QMessageBox.Ok)

class PullPlot(QDialog):
    def __init__(self, df: pd.DataFrame, fig_title, parent = None):
        super().__init__(parent)
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
        self.create_main_layout()

    def create_main_layout(self):
        main_layout = QHBoxLayout()
        left_layout = QGroupBox('Curves')
        left_layout.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        left_wrap_layout = QVBoxLayout()
        left_scrollbox_layout = QVBoxLayout()
        left_scrollbox = QScrollArea()
        scroll_content = QWidget()

        self.col_checkboxes = [QCheckBox(col) for col in self.col_names.keys()]
        [x.stateChanged.connect(self.curveCheckBoxChanged) for x in self.col_checkboxes]
        [left_scrollbox_layout.addWidget(x) for x in self.col_checkboxes]

        scroll_content.setLayout(left_scrollbox_layout)
        left_scrollbox.setWidget(scroll_content)
        left_wrap_layout.addWidget(left_scrollbox)

        left_layout.setLayout(left_wrap_layout)

        right_widget = QWidget()
        right_layout = QVBoxLayout()
        self.plot_widget = MultiPlotFigure(title = self.fig_title)
        toolbar = NavigationToolbar(self.plot_widget, self)
        unwanted_btns = ['Subplots']
        for x in toolbar.actions():
            if x.text() in unwanted_btns:
                toolbar.removeAction(x)
        right_layout.addWidget(toolbar)
        right_layout.addWidget(self.plot_widget)
        right_widget.setLayout(right_layout)

        main_layout.addWidget(left_layout)
        main_layout.addWidget(right_widget)
        self.setLayout(main_layout)

    def curveCheckBoxChanged(self):
        current_widget = self.sender()
        requested_plot = current_widget.text()
        widget_states = [x.isChecked() for x in self.col_checkboxes]
        if widget_states.count(True) > 1:
            # Two boxes checked, disable others
            [x.setDisabled(True) for x in self.col_checkboxes if not x.isChecked()]
        else:
            # Enable all checkboxes
            [x.setDisabled(False) for x in self.col_checkboxes]
        last_plots = self.active_plots
        requested_plots = [x for x in self.col_checkboxes if x.isChecked()]
        if len(requested_plots) == 0:
            # Removing all plots
            self.plot_widget.clear_plot(-1)
            self.active_plots = [None, None]
        elif len(requested_plots) > len(list(filter(bool, last_plots))):
            # Add an additional plot
            plot_index = last_plots.index(None)
            self.active_plots[plot_index] = requested_plot
            self.plot_widget.plot_index(self.x_values, self.df[requested_plot], plot_index, y_text = requested_plot, legend_text = self.col_names[requested_plot]['name'])
        else:
            # Removing a plot
            plot_index = last_plots.index(requested_plot)
            self.active_plots[plot_index] = None
            if plot_index == 0:
                self.active_plots = [self.active_plots[1], None]
            remaining_plot = self.active_plots[0]
            self.plot_widget.clear_plot(-1)
            self.plot_widget.plot_index(self.x_values, self.df[remaining_plot], 0, y_text = remaining_plot, legend_text = self.col_names[remaining_plot]['name'])

class WidgetGallery(QWidget):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.create_main_layout()
        self.presscount = 0
        self.datalogfile = ''
        self.settings = QSettings('nwgruber', 'Datalog Reader')
        if self.settings.contains('last_log_dir'):
            self.last_log_dir = self.settings.value('last_log_dir')
        else:
            self.last_log_dir = ''

    def create_main_layout(self):
        main_layout = QVBoxLayout()
        self.main_widget = QTabWidget()

        self.create_start_tab()
        main_layout.addWidget(self.main_widget)
        self.setLayout(main_layout)

    def create_start_tab(self):
        start_tab = QWidget()
        self.start_tab_layout = QVBoxLayout()
        # Start box
        startbox = QGroupBox('File')
        startbox_layout = QVBoxLayout()
        self.file_label = QLabel('No file selected')
        self.file_btn = QPushButton('Select a Datalog')
        self.file_label.setBuddy(self.file_btn)

        self.file_btn.clicked.connect(self.file_btn_pressed)

        startbox_layout.addWidget(self.file_label)
        startbox_layout.addWidget(self.file_btn)
        startbox.setLayout(startbox_layout)
        # Options box
        optsbox = QGroupBox('Options')
        optsbox_layout = QFormLayout()

        self.throttle_input = DoubleLineEdit(1.0, 100.0, 2)
        self.throttle_input.setToolTip('Omit data when throttle is below this number')
        self.throttle_input.setText('50')

        self.time_filter_input = DoubleLineEdit(0.001, 10.0, 3)
        self.time_filter_input.setToolTip('Omit pulls whose duration is less than this number')
        self.time_filter_input.setText('0.5')

        self.start_btn = QPushButton('Start')
        self.start_btn.clicked.connect(self.start_btn_pressed)

        self.optsbox_disabled(True)
        optsbox_layout.addRow('Throttle Threshold:', self.throttle_input)
        optsbox_layout.addRow('Time Filter:', self.time_filter_input)
        optsbox_layout.addRow(self.start_btn)
        optsbox.setLayout(optsbox_layout)

        self.start_tab_layout.addWidget(startbox)
        self.start_tab_layout.addWidget(optsbox)
        start_tab.setLayout(self.start_tab_layout)

        self.main_widget.addTab(start_tab, 'Start')

    def file_btn_pressed(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setNameFilter('Datalogs (*.csv)')
        if bool(self.last_log_dir):
            dialog.setDirectory(self.last_log_dir)

        if dialog.exec_():
            self.datalogfile = dialog.selectedFiles()[0]
            self.file_label.setText('File: ' + self.datalogfile.rpartition('/')[2])
            self.settings.setValue('last_log_dir', self.datalogfile.rpartition('/')[0])
            self.optsbox_disabled(False)

    def start_btn_pressed(self):
        [self.datalog, self.ap_info] = read_datalog(self.datalogfile)
        self.throttle_input.validate_input()
        self.time_filter_input.validate_input()
        # Get pulls
        self.pulls = get_pulls(self.datalog, self.throttle_input.value(), self.time_filter_input.value())
        if bool(self.pulls):
            # create second tab
            self.pull_info = get_pull_info(self.pulls)
            if self.main_widget.count() == 1:
                self.create_graphtab()
            else:
                self.update_graphtab()
            self.main_widget.setCurrentIndex(1)
        else:
            msg = ErrorMsg('No pulls found in datalog.', infotext = 'Your throttle threshold is too low or time filter too high.')
            msg.exec_()


    def optsbox_disabled(self, disabled):
        self.throttle_input.setDisabled(disabled)
        self.time_filter_input.setDisabled(disabled)
        self.start_btn.setDisabled(disabled)

    def create_graphtab(self):
        self.graphtab = QWidget()
        graph_tab_layout = QVBoxLayout()
        graph_tabbox = QGroupBox('Create Plot')
        graph_tabbox_layout = QFormLayout()

        self.pull_picker = QComboBox()
        self.pull_start_label = QLabel()
        self.pull_duration_label = QLabel()
        self.plot_btn = QPushButton('Plot')
        self.plot_btn.clicked.connect(self.plot_btn_pressed)
        self.update_graphtab()
        self.pull_picker.activated.connect(self.pull_picker_changed)

        graph_tabbox_layout.addRow('Pull:', self.pull_picker)
        graph_tabbox_layout.addRow(self.pull_start_label)
        graph_tabbox_layout.addRow(self.pull_duration_label)
        graph_tabbox_layout.addRow(self.plot_btn)
        graph_tabbox.setLayout(graph_tabbox_layout)
        graph_tab_layout.addWidget(graph_tabbox)
        self.graphtab.setLayout(graph_tab_layout)
        self.main_widget.addTab(self.graphtab, 'Graph')

    def update_graphtab(self):
        formspec = '{:<.2f}'
        pull_picker_items = [str(x) for x in self.pull_info.keys()]
        self.pull_picker.clear()
        self.pull_picker.addItems(pull_picker_items)
        start = formspec.format(self.pull_info[1]['start'])
        duration = formspec.format(self.pull_info[1]['duration'])
        self.pull_start_label.setText(f'Start: {start} sec')
        self.pull_duration_label.setText(f'Duration: {duration} sec')

    def pull_picker_changed(self):
        formspec = '{:<.2f}'
        i = self.pull_picker.currentIndex()
        selected_pull = self.pull_info[i + 1]
        start = formspec.format(selected_pull['start'])
        duration = formspec.format(selected_pull['duration'])
        self.pull_start_label.setText(f'Start: {start} sec')
        self.pull_duration_label.setText(f'Duration: {duration} sec')

    def plot_btn_pressed(self):
        selected_pull = self.pull_picker.currentIndex()
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
