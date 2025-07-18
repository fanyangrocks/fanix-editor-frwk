import collections

from PySide6 import QtWidgets

from .diff import list_diff
from .widget import DebugDialog


class _Unintialized(object):
    pass


class ViewBase(object):
    UNINTIALIZED = _Unintialized()

    def __init__(self, submit_data_callback=None):
        self._submit_data_callback = submit_data_callback
        self._view_children = {}
        self._view_children_data = {}
        self._old_data = self.UNINTIALIZED
        self._current_data = self.UNINTIALIZED
        self._in_refresh = False
        self._should_refresh_internally = False
        self._create_child_view()
        self._widget = self._create_widget()

    @property
    def widget(self):
        return self._widget

    def _create_widget(self):
        raise NotImplementedError(
            "This method should be implemented in subclass")

    def _create_child_view(self):
        pass

    def bind_child_view(self, view, data_converter):
        self._view_children[view] = data_converter
        return view

    def unbind_child_view(self, view):
        del self._view_children[view]
        self._view_children_data.pop(view, None)

    def iter_child_view(self):
        for view in self._view_children:
            yield view

    def set_current_data(self, data):
        self.set_old_data(self._current_data)
        self._current_data = data

    def get_current_data(self):
        return self._current_data

    def set_old_data(self, data):
        self._old_data = data

    def get_old_data(self):
        return self._old_data

    def should_refresh_internally(self):
        return self._should_refresh_internally

    def mark_should_refresh_internally(self, flag):
        self._should_refresh_internally = flag

    def should_refresh(self, new_data, current_data):
        return new_data is not current_data

    def should_refresh_children(self):
        return True

    def _on_try_refresh_child(self, child_view, child_data):
        if not child_view:
            return
        child_view.try_refresh(child_data)

    def try_refresh(self, new_data):
        if self.should_refresh_internally() or (
                self.should_refresh(new_data, self.get_current_data())):
            self.set_current_data(new_data)
            self._in_refresh = True
            self.refresh(new_data)
            self._in_refresh = False
            self.mark_should_refresh_internally(False)
        if self.should_refresh_children():
            for view, data_converter in self._view_children.items():
                self._view_children_data[view] = data_converter(new_data)
            for view, data in self._view_children_data.items():
                self._on_try_refresh_child(view, data)

    def refresh(self, new_data):
        pass

    def submit_data(self, new_data, record_in_history=True):
        if self._submit_data_callback and self.data_valid(new_data):
            self._submit_data_callback(new_data, record_in_history)

    def data_valid(self, new_data):
        return True


class ListViewBase(ViewBase):
    def __init__(self, element_view_factory, submit_data_callback=None):
        super(ListViewBase, self).__init__(submit_data_callback)
        self._element_view_factory = element_view_factory
        self._current_key_list = []
        self._current_element_view_list = []
        self._current_element_view_index = {}
        self._current_element_view_data = []
        self._selected_key = None

    def _on_selection_changed(self, index):
        pass

    def _create_widget(self):
        list_widget = QtWidgets.QListWidget()
        list_widget.itemSelectionChanged.connect(
            self._on_item_selection_changed)
        return list_widget

    def get_selected_data(self):
        index = self.widget.currentRow()
        current_data = self.get_current_data()
        try:
            key = self._current_key_list[index]
            data = self._get_data_at(index, key, current_data)
        except IndexError:
            data = None
        return data

    def _insert_item(self, index, item):
        self.widget.insertItem(index, item)

    def _take_item(self, index):
        return self.widget.takeItem(index)

    def _create_element_view(self):
        return self._element_view_factory()

    def _get_element_view_index(self, element_view):
        return self._current_element_view_index[element_view]

    def _set_current_row(self, index):
        if self.widget.currentRow() != index:
            self.widget.setCurrentRow(index)

    def _clear_selection(self):
        self.widget.setCurrentRow(-1)

    def _generate_key_list(self, data):
        raise NotImplementedError(
            "This method should be implemented in sub-class.")

    def _get_data_at(self, index, key, data_collection):
        raise NotImplementedError(
            "This method should be implemented in sub-class.")

    def try_refresh(self, new_data_collection, selected_key=None):
        if not self._in_refresh:
            self._in_refresh = True
            super(ListViewBase, self).try_refresh(new_data_collection)
            self.refresh_children()
            if self._current_key_list and self._selected_key != selected_key:
                if selected_key is not None:
                    selected_row = None
                    for i, each_key in enumerate(self._current_key_list):
                        if each_key == selected_key:
                            selected_row = i
                            break
                    if selected_row is not None:
                        self._set_current_row(selected_row)
                    else:
                        self._clear_selection()
                else:
                    self._clear_selection()
                self._selected_key = selected_key
            self._in_refresh = False

    def refresh(self, new_data_collection):
        # self._clear_selection()
        self._selected_key = None
        current_keys = self._current_key_list
        current_views = self._current_element_view_list
        new_keys = self._generate_key_list(new_data_collection)
        moves = list_diff(current_keys, new_keys, lambda k: k)
        view_cache = collections.defaultdict(list)
        for index, operation, key in moves:
            if operation == -1:
                if __debug__:
                    del current_keys[index]
                element_view = current_views.pop(index)
                self._take_item(index)
                view_cache[key].append(element_view)
            else:
                if __debug__:
                    current_keys.insert(index, key)
                if view_cache[key]:
                    element_view = view_cache[key].pop()
                else:
                    element_view = self._create_element_view()
                current_views.insert(index, element_view)
                self._insert_item(index, element_view.widget)
        if __debug__:
            assert current_keys == new_keys
        self._current_key_list = new_keys
        self._current_element_view_list = current_views
        self._current_element_view_index.clear()
        self._current_element_view_data = [None] * len(
            self._current_element_view_list)
        for i, element_view in enumerate(self._current_element_view_list):
            self._current_element_view_index[element_view] = i
            self._current_element_view_data[i] = self._get_data_at(
                i, self._current_key_list[i], new_data_collection)

    def refresh_children(self):
        for i, data in enumerate(self._current_element_view_data):
            self._current_element_view_list[i].try_refresh(data)

    def iter_child_view(self):
        for view in self._current_element_view_list:
            yield view

    def _on_item_selection_changed(self):
        if not self._in_refresh:
            row = self.widget.currentRow()
            self._on_selection_changed(row)


class FormEditViewBase(ViewBase):
    def __init__(self, submit_data_callback):
        super(FormEditViewBase, self).__init__(submit_data_callback)
        self.init_item_edit()

    def _create_widget(self):
        self._form_layout = QtWidgets.QFormLayout()
        widget = QtWidgets.QWidget()
        widget.setLayout(self._form_layout)
        return widget

    @property
    def widget(self):
        return self._widget

    def init_item_edit(self):
        pass

    def append_item_edit(self, label, key, view_factory):
        view = view_factory(
            lambda new_v, record_in_history=True: self._update_item(
                key, new_v, record_in_history))
        self.add_row(label, view.widget)
        self.bind_child_view(view, lambda data: getattr(data, key))

    def add_row(self, name, widget):
        label = QtWidgets.QLabel(name)
        self._form_layout.addRow(label, widget)

    def _update_item(self, key, new_v, record_in_history):
        current_data = self.get_current_data()
        if current_data is not self.UNINTIALIZED:
            new_data = current_data.set(key, new_v)
            self.submit_data(new_data, record_in_history=record_in_history)

    def refresh(self, new_data):
        pass


class DebugViewTree(ViewBase):
    def __init__(self, submit_data_callback=None):
        super(DebugViewTree, self).__init__(submit_data_callback)
        self._view_item = {}
        self._children = {}

    def _create_widget(self):
        widget = QtWidgets.QTreeWidget()
        widget.setColumnCount(3)
        widget.setHeaderLabels(["View", "Data", "Submit data function"])
        return widget

    def refresh(self, view_data):
        tree = self.widget
        if view_data.id_ not in self._view_item:
            self._add_view(view_data, tree)
        self._update_view(view_data, self._view_item[view_data.id_])

    def _add_view(self, view, parent):
        item = QtWidgets.QTreeWidgetItem(parent)
        self._view_item[view.id_] = item

    def _update_view(self, view, item):
        item.setText(0, view.name)
        item.setText(1, str(view.data))
        item.setText(2, str(view.submit_callback))

        old_children = self._children.pop(view.id_, [])
        new_children = {}
        for child_view in view.child_views:
            new_children[child_view.id_] = child_view
        removed_children = []
        for child_id in old_children:
            if child_id not in new_children:
                removed_children.append(child_id)
        for child_id in removed_children:
            child_item = self._remove_view(child_id)
            item.removeChild(child_item)
        for child_id, child_view in new_children.items():
            if child_id not in old_children:
                self._add_view(child_view, item)
        for child_id, child_view in new_children.items():
            self._update_view(child_view, self._view_item[child_id])
        self._children[view.id_] = new_children

    def _remove_view(self, view_id):
        for child_id in self._children.pop(view_id, []):
            self._remove_view(view_id)
        return self._view_item.pop(view_id, None)


class DebugView(ViewBase):
    def _create_child_view(self):
        self._tree_view = DebugViewTree()
        self.bind_child_view(self._tree_view, lambda data: data)

    def _create_widget(self):
        dialog = DebugDialog()
        dialog.setTreeWidget(self._tree_view.widget)
        dialog.setMinimumSize(500, 400)
        return dialog
