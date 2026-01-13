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
    QMenu, QStyledItemDelegate, QStyleOptionViewItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QPoint, QItemSelection, QEvent
from PyQt6.QtGui import QUndoStack, QPainter
from theme_editor.models.theme_model import ThemeModel
from theme_editor.models.element import (
    ElementType, BackgroundImageElement, BackgroundVideoElement
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
        # Using simple text for now, can be replaced by QIcon/drawPixmap
        if visible:
            painter.drawText(eye_rect, Qt.AlignmentFlag.AlignCenter, "👁") # Open
        else:
            painter.drawText(eye_rect, Qt.AlignmentFlag.AlignCenter, "⦸") # Closed/Hidden
        
        # Draw lock icon
        lock_rect = option.rect.adjusted(
            rect.width() - self.ICON_SIZE - self.ICON_PADDING, 0, 0, 0
        )
        if locked:
            painter.drawText(lock_rect, Qt.AlignmentFlag.AlignCenter, "🔒") # Closed Lock
        else:
            painter.drawText(lock_rect, Qt.AlignmentFlag.AlignCenter, "🔓") # Open Lock

    def editorEvent(self, event: QEvent, model: ThemeModel, option: QStyleOptionViewItem, index: QModelIndex) -> bool:
        """Handle mouse clicks on icons."""
        if event.type() == QEvent.Type.MouseButtonRelease:
            mouse_event = event
            pos = mouse_event.position().toPoint()
            rect = option.rect
            
            # Icon areas
            eye_rect = option.rect.adjusted(
                rect.width() - 2 * (self.ICON_SIZE + self.ICON_PADDING), 0,
                -self.ICON_SIZE - self.ICON_PADDING, 0
            )
            lock_rect = option.rect.adjusted(
                rect.width() - self.ICON_SIZE - self.ICON_PADDING, 0, 0, 0
            )
            
            # Check for Eye click
            if eye_rect.contains(pos):
                element_id = index.data(ThemeModel.ElementIdRole)
                visible = index.data(ThemeModel.VisibleRole)
                
                # Use ChangePropertyCommand via the model's stack reference if available
                if hasattr(model, '_undo_stack'):
                    from theme_editor.commands.undo_commands import ChangePropertyCommand
                    cmd = ChangePropertyCommand(
                        model, element_id, "visible", visible, not visible
                    )
                    model._undo_stack.push(cmd)
                    return True # Consumed
            
            # Check for Lock click
            elif lock_rect.contains(pos):
                element_id = index.data(ThemeModel.ElementIdRole)
                locked = index.data(ThemeModel.LockedRole)
                
                if hasattr(model, '_undo_stack'):
                    from theme_editor.commands.undo_commands import ChangePropertyCommand
                    cmd = ChangePropertyCommand(
                        model, element_id, "locked", locked, not locked
                    )
                    model._undo_stack.push(cmd)
                    return True # Consumed
                    
        return super().editorEvent(event, model, option, index)


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
        

        
        
        # Move Up
        self._btn_up = QPushButton("▲")
        self._btn_up.setToolTip("Move Up")
        self._btn_up.setMaximumWidth(30)
        self._btn_up.clicked.connect(self._on_move_up_clicked)
        btn_layout.addWidget(self._btn_up)

        # Move Down
        self._btn_down = QPushButton("▼")
        self._btn_down.setToolTip("Move Down")
        self._btn_down.setMaximumWidth(30)
        self._btn_down.clicked.connect(self._on_move_down_clicked)
        btn_layout.addWidget(self._btn_down)
        
        # Duplicate
        self._btn_dup = QPushButton("⧉") # Copy symbol
        self._btn_dup.setToolTip("Duplicate (Ctrl+D)")
        self._btn_dup.setMaximumWidth(30)
        self._btn_dup.clicked.connect(self._on_duplicate_clicked)
        btn_layout.addWidget(self._btn_dup)

        self._btn_delete = QPushButton("🗑") # Trash can
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
        
        # Shortcuts
        from PyQt6.QtGui import QShortcut, QKeySequence
        
        # Delete shortcut attached to tree view to ensure it catches context
        # Delete shortcut removed (handled globally by MainWindow)
        # self._del_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self._tree_view)
        # self._del_shortcut.activated.connect(self._on_delete_clicked)
    
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
            
            # Move Up/Down
            action_up = menu.addAction("Move Up")
            action_up.triggered.connect(self._on_move_up_clicked)
            
            action_down = menu.addAction("Move Down")
            action_down.triggered.connect(self._on_move_down_clicked)
            
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
        # Use existing command infrastructure
        element = self._model.get_element(element_id)
        if element:
            from theme_editor.commands.undo_commands import ChangePropertyCommand
            cmd = ChangePropertyCommand(
                self._model, element_id, "visible", 
                element.visible, not element.visible
            )
            self._undo_stack.push(cmd)
    
    def _toggle_lock(self, element_id: str) -> None:
        """Toggle element lock state."""
        element = self._model.get_element(element_id)
        if element:
            from theme_editor.commands.undo_commands import ChangePropertyCommand
            cmd = ChangePropertyCommand(
                self._model, element_id, "locked", 
                element.locked, not element.locked
            )
            self._undo_stack.push(cmd)
    
    def _on_move_up_clicked(self) -> None:
        """Move selected element up."""
        indexes = self._tree_view.selectedIndexes()
        if not indexes: return
        # Taking just the first one for simplicity or we iterate
        idx = indexes[0]
        eid = idx.data(ThemeModel.ElementIdRole)
        
        # Calculate new index
        current_row = idx.row()
        if current_row > 0:
            new_row = current_row - 1
            parent_id = idx.parent().internalPointer() if idx.parent().isValid() else None
            
            from theme_editor.commands.undo_commands import ReorderElementCommand
            self._undo_stack.push(ReorderElementCommand(
                self._model, eid, parent_id, new_row
            ))
            # Restore selection
            self.select_elements([eid])

    def _on_move_down_clicked(self) -> None:
        """Move selected element down."""
        indexes = self._tree_view.selectedIndexes()
        if not indexes: return
        idx = indexes[0]
        eid = idx.data(ThemeModel.ElementIdRole)
        
        # Calculate new index
        current_row = idx.row()
        total_rows = self._model.rowCount(idx.parent())
        if current_row < total_rows - 1:
            new_row = current_row + 1
            parent_id = idx.parent().internalPointer() if idx.parent().isValid() else None
            
            from theme_editor.commands.undo_commands import ReorderElementCommand
            self._undo_stack.push(ReorderElementCommand(
                self._model, eid, parent_id, new_row
            ))
            self.select_elements([eid])
    
    def _on_delete_clicked(self) -> None:
        """Delete selected elements (skips protected background elements)."""
        indexes = self._tree_view.selectedIndexes()
        if not indexes:
            return
            
        # Sort by row reverse to preserve indices logic during deletion (safest policy)
        sorted_indexes = sorted(indexes, key=lambda idx: idx.row(), reverse=True)
        
        # Filter valid deletions and unique IDs
        to_delete = []
        seen = set()
        
        for idx in sorted_indexes:
            eid = idx.data(ThemeModel.ElementIdRole)
            if eid and eid not in seen:
                element = self._model.get_element(eid)
                if element and not isinstance(element, (BackgroundImageElement, BackgroundVideoElement)):
                    to_delete.append(eid)
                    seen.add(eid)
        
        if not to_delete:
            return

        # Use a macro for multiple deletes
        if len(to_delete) > 1:
            self._undo_stack.beginMacro("Delete Elements")
            
        from theme_editor.commands.undo_commands import DeleteElementCommand
        
        for eid in to_delete:
            self._undo_stack.push(DeleteElementCommand(self._model, eid))
        
        if len(to_delete) > 1:
            self._undo_stack.endMacro()
    
    def _on_duplicate_clicked(self) -> None:
        """Duplicate selected elements."""
        indexes = self._tree_view.selectedIndexes()
        element_ids = list(set(
            idx.data(ThemeModel.ElementIdRole)
            for idx in indexes
            if idx.data(ThemeModel.ElementIdRole)
        ))
        
        if not element_ids:
            return
            
        if len(element_ids) > 1:
            self._undo_stack.beginMacro("Duplicate Elements")
            
        from theme_editor.commands.undo_commands import DuplicateElementCommand
        
        for eid in element_ids:
            if self._model.get_element(eid):
                self._undo_stack.push(DuplicateElementCommand(self._model, eid))
        
        if len(element_ids) > 1:
            self._undo_stack.endMacro()
    
    def _on_group_clicked(self) -> None:
        """Group selected elements."""
        indexes = self._tree_view.selectedIndexes()
        if not indexes:
            return
            
        element_ids = list(set(
            idx.data(ThemeModel.ElementIdRole)
            for idx in indexes
            if idx.data(ThemeModel.ElementIdRole)
        ))
        
        if not element_ids:
            return
            
        from theme_editor.commands.undo_commands import GroupElementsCommand
        self._undo_stack.push(GroupElementsCommand(self._model, element_ids))
    
    def _on_ungroup_clicked(self) -> None:
        """Ungroup selected group."""
        indexes = self._tree_view.selectedIndexes()
        element_ids = list(set(
            idx.data(ThemeModel.ElementIdRole)
            for idx in indexes
            if idx.data(ThemeModel.ElementIdRole)
        ))
        
        if not element_ids:
            return
            
        # Collect groups
        groups_to_ungroup = []
        for eid in element_ids:
            elem = self._model.get_element(eid)
            if elem and elem.element_type == ElementType.GROUP:
                groups_to_ungroup.append(eid)
        
        if not groups_to_ungroup:
            return

        if len(groups_to_ungroup) > 1:
            self._undo_stack.beginMacro("Ungroup Elements")
            
        from theme_editor.commands.undo_commands import UngroupElementsCommand
        
        for gid in groups_to_ungroup:
            self._undo_stack.push(UngroupElementsCommand(self._model, gid))

        if len(groups_to_ungroup) > 1:
            self._undo_stack.endMacro()
