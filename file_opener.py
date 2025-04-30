import traceback
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, Qt, QThreadPool

"""
1) To use, first instantiate thread pool as QThreadPool.globalInstance()
2) Instantiate QtRunner
3) Connect each signal to a function as desired, i.e.
    worker.signals.result.connect(fn)
4) Finally pass worker to thread pool like thread_pool.start(worker)
"""

class WorkerSignals(QObject):
    """Defines signals for QtRunner object"""
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)


class QtRunner(QRunnable):
    """Allows arbitrary functions to be execute the proper Qt way with arg/kwarg supprt"""
    def __init__(self, fn: function, *args, **kwargs):
        """Create instance for function fn"""
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.kwargs['process_callback'] = self.signals.progress
    
    @pyqtSlot()
    def run(self):
        """Run the function assigned to the working and emit applicable signals"""
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            tb = traceback.format_exc()
            self.signals.error.emit((e, tb))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
