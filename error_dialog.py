from PyQt5.QtWidgets import QMessageBox, QTextEdit

def sentence_case(msg: str) -> str:
    """Capitalize first words of string with period-separated sentences"""
    sentences = msg.split('.')
    for i in range(len(sentences)):
        sentences[i] = sentences[i].capitalize()
    return '. '.join(sentences)


class BetterExceptionDialog(QMessageBox):
    def __init__(self, e: Exception, tb: str = None, parent=None):
        """e is any exception, optional tb is output from traceback.format_exc"""
        super().__init__(parent)
        e_msg = str(e)
        e_msg = sentence_case(e_msg)
        e_title = repr(e).partition('(')[0]
        self.setIcon(QMessageBox.Critical)
        self.setWindowTitle(e_title)
        self.setText(e_msg)
        if tb:
            # pull child QTextEdit from messagebox for detailed text
            # then disable word wrap
            text_edit = self.findChild(QTextEdit)
            if text_edit is not None:
                text_edit.setLineWrapMode(QTextEdit.NoWrap)  # disbale word wrap
                widget_width = 1.1 * (
                    text_edit.document().idealWidth()
                    + text_edit.document().documentMargin()
                    + text_edit.verticalScrollBar().width()
                )
                text_edit.parent().setFixedWidth(int(widget_width))
            else:
                print('unable to find text edit')
        self.setSizeGripEnabled(True)  # BUG: size grip enabled but unable to resize
