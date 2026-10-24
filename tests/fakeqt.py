"""Faux Qt / pyqtgraph / serial, juste assez fidèles pour exécuter le code Python de l'application
(logique, attributs, signatures) sans interface réelle. Ne vérifie PAS le rendu ni la sémantique réelle de Qt."""
import sys
import types


class PolyMeta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        sub = PolyMeta(name, (Poly,), {})
        setattr(cls, name, sub)
        return sub

    def __or__(cls, o):
        return cls

    __ror__ = __and__ = __rand__ = __or__


class Poly(metaclass=PolyMeta):
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        v = Poly()
        self.__dict__[name] = v
        return v

    def __call__(self, *a, **k):
        return Poly()

    def connect(self, fn, *a, **k):
        self.__dict__.setdefault("_slots", []).append(fn)

    def emit(self, *a):
        for fn in list(self.__dict__.get("_slots", [])):
            fn(*a)

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return True

    def __or__(self, o):
        return self

    __ror__ = __and__ = __rand__ = __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __or__

    def __lt__(self, o):
        return False

    __gt__ = __le__ = __ge__ = __lt__

    def __index__(self):
        return 0

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0


class Sig:
    def __init__(self):
        self.slots = []

    def connect(self, fn, *a, **k):
        self.slots.append(fn)

    def emit(self, *a):
        for fn in list(self.slots):
            fn(*a)


class SigHolder(Poly):
    """Poly dont certains attributs sont de vrais signaux."""
    _sigs = ("toggled", "currentIndexChanged", "valueChanged", "clicked", "textChanged", "itemChanged",
            "itemSelectionChanged", "currentTextChanged", "cellDoubleClicked")

    def __getattr__(self, name):
        if name in self._sigs:
            s = Sig()
            self.__dict__[name] = s
            return s
        return Poly.__getattr__(self, name)


class FakeCheck(SigHolder):
    def __init__(self, *a, **k):
        self._v, self._en = False, True

    def setEnabled(self, v):
        self._en = bool(v)

    def isEnabled(self):
        return self._en

    def setChecked(self, v):
        v = bool(v)
        if v != self._v:
            self._v = v
            self.toggled.emit(v)

    def isChecked(self):
        return self._v


class FakeSpin(SigHolder):
    def __init__(self, *a, **k):
        self._v, self._lo, self._hi = 0, -1e9, 1e9

    def setRange(self, lo, hi):
        self._lo, self._hi = lo, hi

    def setValue(self, v):
        v = max(self._lo, min(self._hi, v))
        if v != self._v:
            self._v = v
            self.valueChanged.emit(v)

    def value(self):
        return self._v


class FakeCombo(SigHolder):
    def __init__(self, *a, **k):
        self._items, self._i, self._edit = [], -1, None

    def setEditText(self, t):
        self._edit = t
        self.currentTextChanged.emit(t)

    def addItem(self, txt, data=None):
        self._items.append((txt, data))
        if self._i < 0:
            self._i = 0

    def clear(self):
        self._items, self._i, self._edit = [], -1, None

    def count(self):
        return len(self._items)

    def findData(self, d):
        for i, (_t, x) in enumerate(self._items):
            if x == d:
                return i
        return -1

    def itemData(self, i):
        return self._items[i][1] if 0 <= i < len(self._items) else None

    def itemText(self, i):
        return self._items[i][0] if 0 <= i < len(self._items) else ""

    def setCurrentIndex(self, i):
        if i != self._i and 0 <= i < len(self._items):
            self._i = i
            self.currentIndexChanged.emit(i)

    def setCurrentText(self, t):
        for i, (tx, _d) in enumerate(self._items):
            if tx == t:
                self._i = i

    def currentIndex(self):
        return self._i

    def currentData(self):
        return self._items[self._i][1] if 0 <= self._i < len(self._items) else None

    def currentText(self):
        if self._edit is not None:
            return self._edit
        return self._items[self._i][0] if 0 <= self._i < len(self._items) else ""

    def blockSignals(self, b):
        return False


class FakeLabel(SigHolder):
    def __init__(self, text="", *a, **k):
        self._t = text if isinstance(text, str) else ""

    def setText(self, t):
        if t != self._t:
            self._t = t
            self.textChanged.emit(t)        # comme QLineEdit (QLabel n'a personne de connecté)

    def text(self):
        return self._t


class FakeItem(Poly):
    def __init__(self, text="", *a, **k):
        self._t, self._r, self._c, self._tip, self._cs = text, 0, 0, "", None

    def text(self):
        return self._t

    def setText(self, t):
        self._t = t

    def row(self):
        return self._r

    def column(self):
        return self._c

    def toolTip(self):
        return self._tip

    def setToolTip(self, t):
        self._tip = t

    def checkState(self):
        return self._cs

    def setCheckState(self, s):
        self._cs = s

    def setData(self, *a):
        self._d = a[-1]

    def data(self, *a):
        return getattr(self, "_d", None)


class FakeTable(SigHolder):
    def __init__(self, rows=0, cols=0, *a, **k):
        self._rows, self._cols, self._it, self._hidden = rows, cols, {}, {}

    def setRowCount(self, n):
        self._rows = n
        self._it = {k: v for k, v in self._it.items() if k[0] < n}

    def rowCount(self):
        return self._rows

    def insertRow(self, r):
        self._rows += 1
        self._it = {((k[0] + 1 if k[0] >= r else k[0]), k[1]): v for k, v in self._it.items()}

    def removeRow(self, r):
        self._rows -= 1
        self._it = {((k[0] - 1 if k[0] > r else k[0]), k[1]): v for k, v in self._it.items() if k[0] != r}

    def setItem(self, r, c, it):
        it._r, it._c = r, c
        self._it[(r, c)] = it

    def item(self, r, c):
        return self._it.get((r, c))

    def isRowHidden(self, r):
        return self._hidden.get(r, False)

    def setRowHidden(self, r, h):
        self._hidden[r] = h

    def currentRow(self):
        return -1

    def selectedIndexes(self):
        return []

    def horizontalHeaderItem(self, c):
        return Poly()


class FakeTreeItem(Poly):
    def __init__(self, *a, **k):
        self._txt, self._d, self._kids, self._tree, self._sel, self._fg = "", None, [], None, False, None

    def text(self, c=0):
        return self._txt

    def setText(self, c, t=None):
        self._txt = t if t is not None else c

    def setData(self, c, role, v):
        self._d = v

    def data(self, c=0, role=None):
        return self._d

    def addChild(self, it):
        it._tree = self._tree
        self._kids.append(it)

    def setSelected(self, v):
        v = bool(v)
        if v != self._sel:
            self._sel = v
            if self._tree is not None:
                self._tree.itemSelectionChanged.emit()

    def isSelected(self):
        return self._sel

    def setForeground(self, c, b=None):
        self._fg = b


class FakeTree(SigHolder):
    def __init__(self, *a, **k):
        self.top = []
        self.itemSelectionChanged = Sig()
        self._at = None

    def clear(self):
        was = any(i._sel for i in self.all_items())
        self.top = []
        if was:
            self.itemSelectionChanged.emit()

    def addTopLevelItem(self, it):
        it._tree = self
        self.top.append(it)

    def all_items(self):
        out = []

        def rec(it):
            out.append(it)
            for k in it._kids:
                rec(k)
        for t in self.top:
            rec(t)
        return out

    def selectedItems(self):
        return [i for i in self.all_items() if i._sel]

    def clearSelection(self):
        for i in self.all_items():
            i._sel = False
        self.itemSelectionChanged.emit()

    def itemAt(self, pos):
        return self._at

    def expandAll(self):
        pass


class FakeList(SigHolder):
    def __init__(self, *a, **k):
        self._its = []

    def addItem(self, it):
        self._its.append(it)

    def item(self, i):
        return self._its[i]

    def count(self):
        return len(self._its)


class _CheckSig(Sig):
    """triggered.emit(b) d'un test = clic qui met la case dans l'état b (comme le vrai Qt avant le signal)."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def emit(self, *a):
        if a and isinstance(a[0], bool):
            self.owner._c = a[0]
        super().emit(*a)


class FakeAction(Poly):
    def __init__(self, text=""):
        self._t, self._d, self._c = text, None, False
        self.triggered = _CheckSig(self)

    def setChecked(self, c):
        self._c = bool(c)

    def isChecked(self):
        return self._c

    def text(self):
        return self._t

    def setData(self, d):
        self._d = d

    def data(self):
        return self._d


class FakeMenu(Poly):
    chooser = None            # fonction(menu) -> action choisie (ou None)

    def __init__(self, *a, **k):
        self._acts, self._subs, self._title = [], [], ""

    def addAction(self, *a):
        txt = next((x for x in reversed(a) if isinstance(x, str)), "")
        act = FakeAction(txt)
        self._acts.append(act)
        return act

    def addMenu(self, *a):
        sub = a[0] if (a and isinstance(a[0], FakeMenu)) else FakeMenu()
        if a and isinstance(a[-1], str):
            sub._title = a[-1]
        self._subs.append(sub)
        return sub

    def setTitle(self, t):
        self._title = t

    def addSeparator(self):
        pass

    def all_actions(self):
        out = list(self._acts)
        for s2 in self._subs:
            out += s2.all_actions()
        return out

    def exec(self, *a):
        return FakeMenu.chooser(self) if FakeMenu.chooser else None


class FakeLine(Poly):
    def __init__(self, pos=0, *a, **k):
        self._v = pos
        self.sigPositionChanged = Sig()

    def value(self):
        return self._v

    def setValue(self, v):
        self._v = v


class FakeText(Poly):
    def __init__(self, text="", *a, **k):
        self.txt, self.vis, self.pos = text, True, None

    def setText(self, t, color=None):
        self.txt = t

    def setPos(self, x, y):
        self.pos = (x, y)

    def setVisible(self, v):
        self.vis = bool(v)


class FakeCurve(Poly):
    def __init__(self, *a, **k):
        self.x = self.y = None

    def setData(self, x=None, y=None, *a, **k):
        self.x, self.y = x, y


class FakeVB(Poly):
    def __init__(self):
        self.xr, self.yr, self.mx = [470.0, 694.0], [-120.0, -10.0], 480.0
        self.sigXRangeChanged, self.sigResized = Sig(), Sig()

    def viewRange(self):
        return [list(self.xr), list(self.yr)]

    def width(self):
        return 900.0

    def mapSceneToView(self, pos):
        class P:
            def x(s2):
                return self.mx
        return P()


class FakePlotItem(Poly):
    def __init__(self):
        self.vb = FakeVB()
        self.items = []

    def addItem(self, it, *a, **k):
        self.items.append(it)

    def removeItem(self, it):
        if it in self.items:
            self.items.remove(it)

    def plot(self, *a, **k):
        c = FakeCurve()
        self.items.append(c)
        return c

    def setXRange(self, a, b, padding=0):
        self.vb.xr = [a, b]

    def setYRange(self, a, b, padding=0):
        self.vb.yr = [a, b]


class FakeRect(Poly):
    def contains(self, pos):
        return True


class FakePlotWidget(Poly):
    def __init__(self, *a, **k):
        self._pi = FakePlotItem()

    def getPlotItem(self):
        return self._pi

    def sceneBoundingRect(self):
        return FakeRect()

    def scene(self):
        return Poly()


def make_mod(name, **explicit):
    m = type(name, (types.ModuleType,), {})(name)

    def ga(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        sub = PolyMeta(n, (Poly,), {})
        setattr(self, n, sub)
        return sub

    type(m).__getattr__ = ga
    for k, v in explicit.items():
        setattr(m, k, v)
    return m


def install():
    QtWidgets = make_mod("PySide6.QtWidgets", QCheckBox=FakeCheck, QSpinBox=FakeSpin, QDoubleSpinBox=FakeSpin,
                         QComboBox=FakeCombo, QLabel=FakeLabel, QLineEdit=FakeLabel, QTableWidget=FakeTable,
                         QTableWidgetItem=FakeItem, QTreeWidget=FakeTree, QTreeWidgetItem=FakeTreeItem,
                         QListWidget=FakeList, QListWidgetItem=FakeItem, QRadioButton=FakeCheck,
                         QMenu=FakeMenu, QPushButton=FakeLabel)
    QtCore = make_mod("PySide6.QtCore")
    QtGui = make_mod("PySide6.QtGui")
    pyside = make_mod("PySide6", QtWidgets=QtWidgets, QtCore=QtCore, QtGui=QtGui)
    pg = make_mod("pyqtgraph", PlotWidget=FakePlotWidget, InfiniteLine=FakeLine, TextItem=FakeText,
                  PlotCurveItem=FakeCurve)
    pg_exp = make_mod("pyqtgraph.exporters")
    pg.exporters = pg_exp
    serial = make_mod("serial")
    tools = make_mod("serial.tools")
    lp = make_mod("serial.tools.list_ports", comports=lambda: [])
    serial.tools = tools
    tools.list_ports = lp
    for n, m in (("PySide6", pyside), ("PySide6.QtWidgets", QtWidgets), ("PySide6.QtCore", QtCore),
                 ("PySide6.QtGui", QtGui), ("pyqtgraph", pg), ("pyqtgraph.exporters", pg_exp),
                 ("serial", serial), ("serial.tools", tools), ("serial.tools.list_ports", lp)):
        sys.modules[n] = m
    return QtWidgets, QtCore, QtGui, pg
