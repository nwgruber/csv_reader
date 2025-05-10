import sys
import traceback
from typing import Iterable, Union
import matplotlib
matplotlib.use('Qt5Agg')
import pandas as pd
from PyQt5.QtCore import Qt, QSettings, QSize
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
        QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSizePolicy, QScrollArea, QTabWidget, QToolTip, QVBoxLayout, QWidget)
#import pyqtgraph as pg
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from lib import read_datalog, get_pulls, get_pull_info
from error_dialog import BetterExceptionDialog


class MultiPlotFigure(FigureCanvasQTAgg):
    """Extension of FigureCanvasQTAgg with shorthand methods to ease dynamic plotting"""
    def __init__(self, title: str = '', parent=None):
        fig = Figure()
        self.title = title
        self.axes = fig.add_subplot(111)
        self.axes2 = self.axes.twinx()
        self.axes_refs = [self.axes, self.axes2]
        super().__init__(fig)
        self.axes.set_xlabel('Time (sec)')
        if bool(title):
            self.axes.set_title(title)
        fig.tight_layout(pad=3)
        self._plot_refs = [None, None]
        self.colors = ['b', 'r']

    def plot_index(self, xdata: Iterable[float], ydata: Iterable[float], fig_num: int, y_text: str = '', legend_text: str = ''):
        """Add curve to figure by index
        Arguments:
        xdata -- x values to plot
        ydata -- y values to ploy
        fig_num -- index of axis to plot on
        Keyword Arguments:
        y_text -- y axis title, defaults to empty string
        legend_text -- nomenclature of curve in the legend, defaults to empty str
        """
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
        if (fig_num == 1) and (current_ax.yaxis.get_label_position() != 'right'):
            current_ax.yaxis.set_label_position('right')
        self.draw()
        # # testing
        # if fig_num == 1:
        #     print(current_ax.yaxis.get_label_position())
        #     print(current_ax.yaxis.label.get_position())

    def clear_plot(self, fig_num: int):
        """Remove curve from figure at given index"""
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
    """Extends QLineEdit to make it more aesthetic and easier to retreive data"""
    def __init__(self, lower: float, upper: float, decimals: int, parent=None):
        """Initialize instance
        Arguments:
        lower -- float, min acceptible value
        upper -- float, max acceptible value
        decimals -- int, number of decimals to allow
        """
        super().__init__(parent)
        self.double_validator = QDoubleValidator(lower, upper, decimals)
        self.setValidator(self.double_validator)

    def validate_input(self):
        """Validate input and update displayed value"""
        if self.text() != '':
            try:
                value = float(self.text())
            except ValueError:
                value = 0
            finally:
                # Update extremas to int if no decimal is required
                lower = self.double_validator.bottom()
                if lower.is_integer():
                    lower = int(lower)
                upper = self.double_validator.top()
                if upper.is_integer():
                    upper = int(upper)
                # Update displayed value to respective limit if input is out of bounds
                if value > upper:
                    self.setText(str(upper))
                elif value < lower:
                    self.setText(str(lower))

    def value(self) -> float:
        """Return user input as float"""
        try:
            return float(self.text())
        except ValueError:
            return 0


class ErrorMsg(QMessageBox):
    """Extends QMessageBox to make error message display easier"""
    def __init__(self, msgtext: str, infotext: str = '', parent=None):
        """Initialize
        Arguments:
        msgtext -- str, error message title
        Keyword arguments:
        infotext -- str, informative text to display, defaults to empty str
        """
        super().__init__(parent)
        self.setIcon(QMessageBox.Critical)
        self.setWindowTitle('Error')
        self.setText(msgtext)
        if bool(infotext):
            self.setInformativeText(infotext)
        self.setStandardButtons(QMessageBox.Ok)


class BetterScrollArea(QScrollArea):
    """Override QScrollArea size hint to make it not suck"""
    def sizeHint(self) -> QSize:
        """Provide a size hint that accounts for vertical scroll bar width"""
        hint = super().sizeHint()
        bar_width = self.verticalScrollBar().sizeHint().width()
        return QSize(hint.width() + bar_width, hint.height())


class PullPlot(QDialog):
    """Dialog with a figure canvas and list of selectable curves to plot"""
    # fig_title: str
    # x_values: pd.Series
    # df: pd.DataFrame
    # col_names: dict
    # active_plots: list
    # axis_selector: QComboBox
    # ymin_input: DoubleLineEdit
    # ymax_input: DoubleLineEdit
    # col_checkboxes: list[QCheckBox]
    # plot_widget: MultiPlotFigure

    def __init__(self, df: pd.DataFrame, fig_title: str, parent=None):
        super().__init__(parent)
        self.fig_title = fig_title
        self.setWindowTitle(fig_title)
        self.x_values = df['Time (sec)']
        self.df = df.drop('Time (sec)', axis=1)
        #print(self.df)
        col_names = {}
        for col in self.df.columns:
            if col.endswith(')'):
                unit_start = col.index('(')
                col_names[col] = {
                    'name': col[:(unit_start - 1)],
                    'unit': col[unit_start:].strip('()')
                }
            else:
                col_names[col] = {
                    'name': col,
                    'unit': None
                }
        self.col_names = col_names
        self.active_plots = [None, None]
        self.create_main_layout()

    def create_main_layout(self):
        """Populate dialog with widgets"""
        # higher level layout
        main_layout = QHBoxLayout()
        left_highlevel_widget = QWidget()
        left_highlevel_layout = QVBoxLayout()
        left_layout = QGroupBox('Curves')
        left_layout.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        left_wrap_layout = QVBoxLayout()
        # scroll area content
        left_scrollbox_layout = QVBoxLayout()
        left_scrollbox = BetterScrollArea()
        scroll_content = QWidget()
        # populate scroll area content
        self.col_checkboxes = [QCheckBox(col) for col in self.col_names.keys()]
        [x.stateChanged.connect(self.curve_checkbox_changed) for x in self.col_checkboxes]
        [left_scrollbox_layout.addWidget(x) for x in self.col_checkboxes]
        # finish scroll area setup
        scroll_content.setLayout(left_scrollbox_layout)
        left_scrollbox.setWidget(scroll_content)
        left_wrap_layout.addWidget(left_scrollbox)
        # left axes options
        left_opts_widget = QGroupBox('Options')
        left_opts_layout = QFormLayout()
        # axis selector
        self.axis_selector = QComboBox()
        self.axis_selector.addItems(['LH Axis', 'RH Axis'])
        left_opts_layout.addRow('Axis', self.axis_selector)
        # y max input
        self.ymax_input = DoubleLineEdit(-1000000, 1000000, 3)
        self.ymax_input.setText('1')
        left_opts_layout.addRow('Y Max', self.ymax_input)
        # y min input
        self.ymin_input = DoubleLineEdit(-1000000, 1000000, 3)
        self.ymin_input.setText('0')
        left_opts_layout.addRow('Y Min', self.ymin_input)
        # finalize left layout
        left_opts_widget.setLayout(left_opts_layout)
        left_opts_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        left_layout.setLayout(left_wrap_layout)
        left_layout.updateGeometry()
        left_highlevel_layout.addWidget(left_layout)
        left_highlevel_layout.addWidget(left_opts_widget)
        left_highlevel_widget.setLayout(left_highlevel_layout)
        left_highlevel_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        # right plot area
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        self.plot_widget = MultiPlotFigure(title=self.fig_title)
        toolbar = NavigationToolbar(self.plot_widget, self)
        unwanted_btns = ['Subplots']
        for x in toolbar.actions():
            if x.text() in unwanted_btns:
                toolbar.removeAction(x)
        right_layout.addWidget(toolbar)
        right_layout.addWidget(self.plot_widget)
        right_widget.setLayout(right_layout)
        # finish setting up high level layout
        main_layout.addWidget(left_highlevel_widget)
        main_layout.addWidget(right_widget)
        self.setLayout(main_layout)
        self.updateGeometry()
        # bind functions
        self.axis_selector.activated.connect(self.axis_selector_changed)
        self.ymin_input.editingFinished.connect(self.ylim_input_changed)
        self.ymax_input.editingFinished.connect(self.ylim_input_changed)
        self.plot_widget.mpl_connect('draw_event', self.draw_event_called)

    def axis_selector_changed(self):
        """Update displayed y axis min/max values"""
        formspec = '{:.2f}'
        i = self.axis_selector.currentIndex()
        if i == 0:
            axes_ref = self.plot_widget.axes
        else:
            axes_ref = self.plot_widget.axes2
        axis_limits = axes_ref.get_ylim()
        self.ymax_input.setText(formspec.format(axis_limits[1]))
        self.ymin_input.setText(formspec.format(axis_limits[0]))

    def ylim_input_changed(self, input_text: str = ''):
        """Update y axis limits per user input"""
        # pull user input values
        self.ymax_input.validate_input()
        self.ymin_input.validate_input()
        new_ymax = self.ymax_input.value()
        new_ymin = self.ymin_input.value()
        # get axis reference and update limits
        i = self.axis_selector.currentIndex()
        if i == 0:
            self.plot_widget.axes.set_ylim(bottom=new_ymin, top=new_ymax)
        else:
            self.plot_widget.axes2.set_ylim(bottom=new_ymin, top=new_ymax)
        # honestly idk wtf this if statement is for
        # if input_text != 'draw':
        self.plot_widget.draw()

    def draw_event_called(self, *arg):
        """Call axis_selector_changed to update displayed axis limits when graph is altered"""
        self.axis_selector_changed()

    def curve_checkbox_changed(self):
        """Update figure when user selects/deselects a variable"""
        current_widget = self.sender()
        requested_plot = current_widget.text()
        widget_states = [x.isChecked() for x in self.col_checkboxes]
        # disable other check boxes when 2 are selected
        if widget_states.count(True) > 1:
            # Two boxes checked, disable others
            [x.setDisabled(True) for x in self.col_checkboxes if not x.isChecked()]
        else:
            # Enable all checkboxes
            [x.setDisabled(False) for x in self.col_checkboxes]
        # draw stuff
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
            self.plot_widget.plot_index(self.x_values, self.df[requested_plot], plot_index,\
                                        y_text=requested_plot, legend_text=self.col_names[requested_plot]['name'])
        else:
            # Removing a plot
            plot_index = last_plots.index(requested_plot)
            self.active_plots[plot_index] = None
            if plot_index == 0:
                self.active_plots = [self.active_plots[1], None]
            remaining_plot = self.active_plots[0]
            self.plot_widget.clear_plot(-1)
            self.plot_widget.plot_index(self.x_values, self.df[remaining_plot], 0, y_text=remaining_plot,\
                                        legend_text = self.col_names[remaining_plot]['name'])
        self.axis_selector_changed()  # update axis limits on change

class WidgetGallery(QWidget):
    def __init__(self, parent=None):
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
        start_box = QGroupBox('File')
        start_box_layout = QVBoxLayout()
        self.file_label = QLabel('No file selected')
        self.file_button = QPushButton('Select a Datalog')
        self.file_label.setBuddy(self.file_button)

        self.file_button.clicked.connect(self.file_button_pressed)

        start_box_layout.addWidget(self.file_label)
        start_box_layout.addWidget(self.file_button)
        start_box.setLayout(start_box_layout)
        # Options box
        opts_box = QGroupBox('Options')
        opts_box_layout = QFormLayout()

        self.throttle_input = DoubleLineEdit(1.0, 100.0, 0)
        self.throttle_input.setToolTip('Omit data when throttle is below this number. Set to 0 to see full dataset.')
        self.throttle_input.setText('50')

        self.time_filter_input = DoubleLineEdit(0.001, 10.0, 3)
        self.time_filter_input.setToolTip('Omit pulls whose duration is less than this number')
        self.time_filter_input.setText('0.5')

        self.start_button = QPushButton('Start')
        self.start_button.clicked.connect(self.start_button_pressed)

        self.opts_box_disabled(True)
        opts_box_layout.addRow('Throttle Threshold:', self.throttle_input)
        opts_box_layout.addRow('Time Filter:', self.time_filter_input)
        opts_box_layout.addRow(self.start_button)
        opts_box.setLayout(opts_box_layout)

        self.start_tab_layout.addWidget(start_box)
        self.start_tab_layout.addWidget(opts_box)
        start_tab.setLayout(self.start_tab_layout)

        self.main_widget.addTab(start_tab, 'Start')

    def file_button_pressed(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setNameFilter('Datalogs (*.csv)')
        if bool(self.last_log_dir):
            dialog.setDirectory(self.last_log_dir)

        if dialog.exec_():
            self.datalogfile = dialog.selectedFiles()[0]
            self.file_label.setText('File: ' + self.datalogfile.rpartition('/')[2])
            self.settings.setValue('last_log_dir', self.datalogfile.rpartition('/')[0])
            self.opts_box_disabled(False)

    def start_button_pressed(self):
        try:
            [self.datalog, self.ap_info] = read_datalog(self.datalogfile)
            self.throttle_input.validate_input()
            self.time_filter_input.validate_input()
            # Get pulls
            self.pulls = get_pulls(self.datalog, self.throttle_input.value(), self.time_filter_input.value())
            if bool(self.pulls):
                # create second tab
                self.pull_info = get_pull_info(self.pulls)
                if self.main_widget.count() == 1:
                    self.create_graph_tab()
                else:
                    self.update_graph_tab()
                self.main_widget.setCurrentIndex(1)
            else:
                error_msg = ErrorMsg('No pulls found in datalog.', infotext = 'Your throttle threshold is too low or time filter too high.')
                error_msg.exec_()
        except Exception as e:
            tb = traceback.format_exc()
            error_msg = BetterExceptionDialog(e, tb)
            error_msg.exec_()


    def opts_box_disabled(self, disabled):
        self.throttle_input.setDisabled(disabled)
        self.time_filter_input.setDisabled(disabled)
        self.start_button.setDisabled(disabled)

    def create_graph_tab(self):
        self.graph_tab = QWidget()
        graph_tab_layout = QVBoxLayout()
        graph_tab_box = QGroupBox('Create Plot')
        graph_tab_box_layout = QFormLayout()

        self.pull_picker = QComboBox()
        self.pull_start_label = QLabel()
        self.pull_duration_label = QLabel()
        self.plot_button = QPushButton('Plot')
        self.plot_button.clicked.connect(self.plot_button_pressed)
        self.update_graph_tab()
        self.pull_picker.activated.connect(self.pull_picker_changed)

        graph_tab_box_layout.addRow('Pull:', self.pull_picker)
        graph_tab_box_layout.addRow(self.pull_start_label)
        graph_tab_box_layout.addRow(self.pull_duration_label)
        graph_tab_box_layout.addRow(self.plot_button)
        graph_tab_box.setLayout(graph_tab_box_layout)
        graph_tab_layout.addWidget(graph_tab_box)
        self.graph_tab.setLayout(graph_tab_layout)
        self.main_widget.addTab(self.graph_tab, 'Graph')

    def update_graph_tab(self):
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

    def plot_button_pressed(self):
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
    app.exec_()

if __name__ == '__main__':
    main()
