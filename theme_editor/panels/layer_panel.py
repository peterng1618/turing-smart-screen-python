# SPDX-License-Identifier: GPL-3.0-or-later
"""
Layer Panel for Theme Editor v2.

Provides a tree view for managing theme layers with:
- Drag-to-reorder layers
- Layer grouping
- Visibility and lock toggles
- Context menu for common operations
"""

import logging
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QPushButton,
    QMenu, QStyledItemDelegate, QStyleOptionViewItem, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QPoint, QItemSelection, QAbstractProxyModel, QSortFilterProxyModel
from PyQt6.QtGui import QUndoStack, QAction, QIcon, QPainter, QMouseEvent

from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import (
    ElementType, create_element,
    BackgroundImageElement, BackgroundVideoElement
)

logger = logging.getLogger(__name__)





class LayerItemDelegate(QStyledItemDelegate):
    """Custom delegate for rendering layer items with visibility/lock icons."""
    
    ICON_SIZE = 16
    ICON_PADDING = 4
    
    def __init__(self, model: ThemeModel, parent=None):
        super().__init__(parent)
        self._model = model
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        """Paint the layer item with icons."""
        # Draw default item
        super().paint(painter, option, index)
        
        # Draw visibility icon on the right
        rect = option.rect
        icon_x = rect.right() - self.ICON_SIZE - self.ICON_PADDING
        icon_y = rect.center().y() - self.ICON_SIZE // 2
        
        # Get element visibility
        visible = index.data(ThemeModel.VisibleRole)
        locked = index.data(ThemeModel.LockedRole)
        
        # Draw eye icon (visibility)
        eye_rect = option.rect.adjusted(
            rect.width() - 2 * (self.ICON_SIZE + self.ICON_PADDING), 0,
            -self.ICON_SIZE - self.ICON_PADDING, 0
        )
        if visible:
            painter.drawText(eye_rect, Qt.AlignmentFlag.AlignCenter, "👁")
        else:
            painter.drawText(eye_rect, Qt.AlignmentFlag.AlignCenter, "👁‍🗨")
        
        # Draw lock icon
        lock_rect = option.rect.adjusted(
            rect.width() - self.ICON_SIZE - self.ICON_PADDING, 0, 0, 0
        )
        if locked:
            painter.drawText(lock_rect, Qt.AlignmentFlag.AlignCenter, "🔒")


class LayerPanel(QWidget):
    """
    Panel for viewing and managing theme layers.
    
    Signals:
        selection_changed: Emitted when layer selection changes
    """
    
    selection_changed = pyqtSignal(list)  # List of selected element IDs
    
    def __init__(
        self,
        model: ThemeModel,
        undo_stack: QUndoStack,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setMinimumWidth(300)
        
        self._model = model
        self._undo_stack = undo_stack
        self._updating_selection = False
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Tree view for layers
        self._tree_view = QTreeView()
        
        # Use model directly (default top-to-bottom order)
        self._tree_view.setModel(self._model)
        
        self._tree_view.setHeaderHidden(True)
        self._tree_view.setDragEnabled(True)
        self._tree_view.setAcceptDrops(True)
        self._tree_view.setDropIndicatorShown(True)
        self._tree_view.setDragDropMode(QTreeView.DragDropMode.InternalMove)
        self._tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self._tree_view.setEditTriggers(
            QTreeView.EditTrigger.DoubleClicked |
            QTreeView.EditTrigger.EditKeyPressed
        )
        self._tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree_view.customContextMenuRequested.connect(self._show_context_menu)
        
        # Set custom delegate
        self._delegate = LayerItemDelegate(self._model, self._tree_view)
        self._tree_view.setItemDelegate(self._delegate)
        
        layout.addWidget(self._tree_view)
        
        # Button bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        

        
        self._btn_delete = QPushButton("−")
        self._btn_delete.setToolTip("Delete selected (Del)")
        self._btn_delete.setMaximumWidth(30)
        self._btn_delete.clicked.connect(self._on_delete_clicked)
        btn_layout.addWidget(self._btn_delete)
        
        self._btn_group = QPushButton("⊞")
        self._btn_group.setToolTip("Group selected (Ctrl+G)")
        self._btn_group.setMaximumWidth(30)
        self._btn_group.clicked.connect(self._on_group_clicked)
        btn_layout.addWidget(self._btn_group)
        
        self._btn_ungroup = QPushButton("⊟")
        self._btn_ungroup.setToolTip("Ungroup selected (Ctrl+Shift+G)")
        self._btn_ungroup.setMaximumWidth(30)
        self._btn_ungroup.clicked.connect(self._on_ungroup_clicked)
        btn_layout.addWidget(self._btn_ungroup)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    def _connect_signals(self) -> None:
        """Connect model and view signals."""
        selection_model = self._tree_view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)
    
    def _on_selection_changed(self) -> None:
        """Handle tree view selection change."""
        if self._updating_selection:
            return
            
        indexes = self._tree_view.selectedIndexes()
        element_ids = [
            idx.data(ThemeModel.ElementIdRole)
            for idx in indexes
            if idx.data(ThemeModel.ElementIdRole)
        ]
        self.selection_changed.emit(element_ids)
    
    def select_elements(self, element_ids: List[str]) -> None:
        """
        Select elements by ID in the tree view.
        
        Args:
            element_ids: List of element IDs to select
        """
        selection_model = self._tree_view.selectionModel()
        if not selection_model:
            return
        
        self._updating_selection = True
        try:
            # Build new selection
            new_selection = QItemSelection()
            for elem_id in element_ids:
                element = self._model.get_element(elem_id)
                if element:
                    source_index = self._model._get_index_for_element(elem_id)
                    if source_index.isValid():
                        new_selection.select(source_index, source_index)
            
            # Apply atomic update
            selection_model.select(
                new_selection,
                selection_model.SelectionFlag.ClearAndSelect | selection_model.SelectionFlag.Rows
            )
            
        finally:
            self._updating_selection = False
    
    def _show_context_menu(self, pos: QPoint) -> None:
        """Show context menu at position."""
        index = self._tree_view.indexAt(pos)
        
        menu = QMenu(self)
        
        if index.isValid():
            element_id = index.data(ThemeModel.ElementIdRole)
            element = self._model.get_element(element_id)
            
            # Rename
            action_rename = menu.addAction("Rename (F2)")
            action_rename.triggered.connect(
                lambda: self._tree_view.edit(index)
            )
            
            menu.addSeparator()
            
            # Visibility toggle
            if element and element.visible:
                action_hide = menu.addAction("Hide")
                action_hide.triggered.connect(
                    lambda: self._toggle_visibility(element_id)
                )
            else:
                action_show = menu.addAction("Show")
                action_show.triggered.connect(
                    lambda: self._toggle_visibility(element_id)
                )
            
            # Lock toggle
            if element and element.locked:
                action_unlock = menu.addAction("Unlock")
                action_unlock.triggered.connect(
                    lambda: self._toggle_lock(element_id)
                )
            else:
                action_lock = menu.addAction("Lock")
                action_lock.triggered.connect(
                    lambda: self._toggle_lock(element_id)
                )
            
            menu.addSeparator()
            
            # Duplicate
            action_duplicate = menu.addAction("Duplicate (Ctrl+D)")
            action_duplicate.triggered.connect(self._on_duplicate_clicked)
            
            # Delete (disabled for background elements)
            action_delete = menu.addAction("Delete (Del)")
            action_delete.triggered.connect(self._on_delete_clicked)
            if isinstance(element, (BackgroundImageElement, BackgroundVideoElement)):
                action_delete.setEnabled(False)
                action_delete.setText("Delete (Protected)")
            
            menu.addSeparator()
            
            # Group/Ungroup
            action_group = menu.addAction("Group (Ctrl+G)")
            action_group.triggered.connect(self._on_group_clicked)
            
            if element and element.element_type == ElementType.GROUP:
                action_ungroup = menu.addAction("Ungroup (Ctrl+Shift+G)")
                action_ungroup.triggered.connect(self._on_ungroup_clicked)
            pass
        
        menu.exec(self._tree_view.mapToGlobal(pos))
    
    def _toggle_visibility(self, element_id: str) -> None:
        """Toggle element visibility."""
        element = self._model.get_element(element_id)
        if element:
            self._model.set_element_property(element_id, "visible", not element.visible)
    
    def _toggle_lock(self, element_id: str) -> None:
        """Toggle element lock state."""
        element = self._model.get_element(element_id)
        if element:
            self._model.set_element_property(element_id, "locked", not element.locked)
    

    
    def _on_delete_clicked(self) -> None:
        """Delete selected elements (skips protected background elements)."""
        indexes = self._tree_view.selectedIndexes()
        for idx in reversed(indexes):
            element_id = idx.data(ThemeModel.ElementIdRole)
            if element_id:
                element = self._model.get_element(element_id)
                # Skip protected background elements
                if isinstance(element, (BackgroundImageElement, BackgroundVideoElement)):
                    logger.debug(f"Skipping delete for protected element: {element.name}")
                    continue
                self._model.remove_element(element_id)
    
    def _on_duplicate_clicked(self) -> None:
        """Duplicate selected elements."""
        # TODO: Implement duplication with undo command
        logger.debug("Duplicate not yet implemented")
    
    def _on_group_clicked(self) -> None:
        """Group selected elements."""
        # TODO: Implement grouping with undo command
        logger.debug("Group not yet implemented")
    
    def _on_ungroup_clicked(self) -> None:
        """Ungroup selected group."""
        # TODO: Implement ungrouping with undo command
        logger.debug("Ungroup not yet implemented")
    
    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Delete:
            self._on_delete_clicked()
        elif event.key() == Qt.Key.Key_F2:
            index = self._tree_view.currentIndex()
            if index.isValid():
                self._tree_view.edit(index)
        else:
            super().keyPressEvent(event)
