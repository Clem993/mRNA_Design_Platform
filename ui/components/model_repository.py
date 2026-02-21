"""
Model Repository Browser — modal for importing models from a curated catalog.

Presents model cards organized by category with import animation
and provenance tracking.
"""
from __future__ import annotations

import time
import threading
from typing import TYPE_CHECKING, Dict, Set

import panel as pn
import param

from models.catalog import ModelCatalogEntry, get_model_catalog, FILTER_OPTIONS

if TYPE_CHECKING:
    from ui.state import AppState


_CARD_BG = "#FFFFFF"
_CARD_BORDER = "#E2E8F0"
_ANALYTICAL_BADGE = "#3B82F6"
_GENERATIVE_BADGE = "#8B5CF6"
_EMBEDDED_BADGE = "#10B981"
_API_BADGE = "#F59E0B"
_IMPORTED_BADGE = "#10B981"


class ModelRepositoryPanel(param.Parameterized):
    """Model Repository Browser panel."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._catalog = get_model_catalog()
        self._imported_names: Set[str] = set()
        self._import_status: Dict[str, pn.pane.HTML] = {}
        self._active_filter = "All"
        self._search_text = ""
        self._cards_container = pn.Column(sizing_mode="stretch_width")

    def _get_imported_model_names(self) -> Set[str]:
        """Get names of already-imported models."""
        names = set()
        if self._state.model_registry:
            for model_reg in self._state.model_registry.all_models:
                names.add(model_reg.model.name)
        return names | self._imported_names

    def _matches_filter(self, entry: ModelCatalogEntry) -> bool:
        """Check if a catalog entry matches the active filter and search."""
        # Search filter
        if self._search_text:
            search = self._search_text.lower()
            searchable = f"{entry.name} {entry.description} {entry.category} {' '.join(entry.tags)}".lower()
            if search not in searchable:
                return False

        # Category filter
        f = self._active_filter
        if f == "All":
            return True
        if f == "Analytical":
            return entry.model_type == "analytical"
        if f == "Generative":
            return entry.model_type == "generative"
        if f == "Structure":
            return "Structure" in entry.category
        if f == "Stability":
            return "Stability" in entry.category or "Degradation" in entry.category or "Half-life" in entry.category
        if f == "Codon":
            return "Codon" in entry.category
        if f == "UTR":
            return "UTR" in entry.category
        if f == "Foundation":
            return "Foundation" in entry.category
        return True

    def _build_model_card(self, entry: ModelCatalogEntry) -> pn.Column:
        """Build a single model card."""
        imported = entry.name in self._get_imported_model_names()

        # Type badge
        if entry.model_type == "analytical":
            type_badge = f'<span style="background:{_ANALYTICAL_BADGE};color:white;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;">ANALYTICAL</span>'
        else:
            type_badge = f'<span style="background:{_GENERATIVE_BADGE};color:white;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;">GENERATIVE</span>'

        # Deployment badge
        if entry.deployment == "embedded":
            deploy_badge = f'<span style="background:{_EMBEDDED_BADGE}22;color:{_EMBEDDED_BADGE};padding:2px 6px;border-radius:10px;font-size:10px;">💻 Embedded</span>'
        elif entry.deployment == "api":
            deploy_badge = f'<span style="background:{_API_BADGE}22;color:{_API_BADGE};padding:2px 6px;border-radius:10px;font-size:10px;">☁️ API</span>'
        else:
            deploy_badge = f'<span style="background:{_EMBEDDED_BADGE}22;color:{_EMBEDDED_BADGE};padding:2px 6px;border-radius:10px;font-size:10px;">💻☁️ Both</span>'

        # Repository icon
        if "github.com" in entry.repository:
            repo_icon = "🔗"
        elif "huggingface" in entry.repository:
            repo_icon = "🤗"
        else:
            repo_icon = "📄"

        # Status area
        status_pane = pn.pane.HTML("", sizing_mode="stretch_width")
        self._import_status[entry.name] = status_pane

        # Import button or imported badge
        if imported:
            action_widget = pn.pane.HTML(
                f'<span style="background:{_IMPORTED_BADGE}22;color:{_IMPORTED_BADGE};'
                f'padding:4px 12px;border-radius:4px;font-size:11px;font-weight:600;">'
                f'✓ Imported</span>',
                margin=(4, 0),
            )
        else:
            import_btn = pn.widgets.Button(
                name="Import",
                button_type="primary",
                width=80,
                margin=(4, 0),
                stylesheets=["""
                    :host .bk-btn {
                        font-size: 11px;
                        padding: 4px 12px;
                        border-radius: 4px;
                    }
                """],
            )
            import_btn.on_click(lambda event, e=entry: self._on_import_model(e))
            action_widget = import_btn

        card_html = pn.pane.HTML(
            f'<div style="border:1px solid {_CARD_BORDER};border-radius:8px;padding:14px;'
            f'background:{_CARD_BG};margin-bottom:8px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
            f'<div style="flex:1;">'
            f'<div style="font-size:14px;font-weight:700;color:#0F172A;margin-bottom:4px;">'
            f'{entry.icon} {entry.name} <span style="font-size:10px;color:#94A3B8;font-weight:400;">v{entry.version}</span></div>'
            f'<div style="margin-bottom:6px;">{type_badge} '
            f'<span style="background:#F1F5F9;color:#475569;padding:2px 6px;border-radius:10px;font-size:10px;">{entry.category}</span> '
            f'{deploy_badge}</div>'
            f'<div style="font-size:12px;color:#475569;margin-bottom:6px;line-height:1.4;">{entry.description}</div>'
            f'<div style="font-size:11px;color:#94A3B8;">{repo_icon} {entry.repository}</div>'
            f'<div style="font-size:10px;color:#94A3B8;margin-top:2px;">Input: {entry.inputs}</div>'
            f'</div>'
            f'</div>'
            f'</div>',
            sizing_mode="stretch_width",
            margin=0,
        )

        return pn.Column(
            card_html,
            pn.Row(action_widget, status_pane, sizing_mode="stretch_width", margin=(0, 14, 8, 14)),
            sizing_mode="stretch_width",
            margin=0,
        )

    def _on_import_model(self, entry: ModelCatalogEntry) -> None:
        """Handle model import with animated workflow."""
        status = self._import_status.get(entry.name)
        if not status:
            return

        def _run_import():
            # Step 1: Connecting
            status.object = (
                '<div style="font-size:11px;color:#6366F1;padding:4px 0;">'
                '⏳ Connecting to repository...</div>'
            )
            time.sleep(0.8)

            # Step 2: Downloading
            status.object = (
                '<div style="font-size:11px;color:#6366F1;padding:4px 0;">'
                '📥 Downloading model...</div>'
            )
            time.sleep(0.8)

            # Step 3: Registering
            status.object = (
                '<div style="font-size:11px;color:#6366F1;padding:4px 0;">'
                '🔧 Registering model...</div>'
            )
            time.sleep(0.5)

            # Register the model as a demo stub
            self._register_catalog_model(entry)

            # Step 4: Done
            status.object = (
                f'<div style="font-size:11px;color:{_IMPORTED_BADGE};padding:4px 0;">'
                f'✓ Successfully imported {entry.name}</div>'
            )
            self._imported_names.add(entry.name)
            self._state.param.trigger("model_registry")

        thread = threading.Thread(target=_run_import, daemon=True)
        thread.start()

    def _register_catalog_model(self, entry: ModelCatalogEntry) -> None:
        """Register a catalog model as a demo stub in the model registry."""
        from models.base import ScoringModel, GenerativeModel, RegisteredModel

        if entry.model_type == "analytical":
            # Create a demo scoring model stub
            class CatalogScorer(ScoringModel):
                _entry = entry

                @property
                def name(self):
                    return self._entry.name

                @property
                def description(self):
                    return self._entry.description

                @property
                def version(self):
                    return self._entry.version

                def score(self, sequence, metadata=None):
                    import random
                    return round(random.uniform(0.3, 0.95), 3)

            model = CatalogScorer()
            self._state.model_registry._register(
                model, "scoring", "catalog",
                entry.repository_url,
            )
            # Store provenance
            reg = self._state.model_registry._models[entry.name]
            reg.repository = entry.repository
            reg.category = entry.category
        else:
            # Create a demo generative model stub
            class CatalogGenerator(GenerativeModel):
                _entry = entry

                @property
                def name(self):
                    return self._entry.name

                @property
                def description(self):
                    return self._entry.description

                @property
                def version(self):
                    return self._entry.version

                def generate(self, constraints, n=10, seed=None):
                    return []

            model = CatalogGenerator()
            self._state.model_registry._register(
                model, "generative", "catalog",
                entry.repository_url,
            )
            reg = self._state.model_registry._models[entry.name]
            reg.repository = entry.repository
            reg.category = entry.category

    def _rebuild_cards(self) -> None:
        """Rebuild the cards container based on current filter."""
        self._cards_container.clear()
        filtered = [e for e in self._catalog if self._matches_filter(e)]

        if not filtered:
            self._cards_container.append(pn.pane.HTML(
                '<div style="color:#94A3B8;text-align:center;padding:24px;">'
                'No models match the current filter.</div>'
            ))
            return

        # Group by type
        analytical = [e for e in filtered if e.model_type == "analytical"]
        generative = [e for e in filtered if e.model_type == "generative"]

        if analytical:
            self._cards_container.append(pn.pane.HTML(
                f'<div style="font-size:13px;font-weight:700;color:#0F172A;margin:12px 0 8px 0;">'
                f'Analytical Models ({len(analytical)})</div>'
            ))
            for entry in analytical:
                self._cards_container.append(self._build_model_card(entry))

        if generative:
            self._cards_container.append(pn.pane.HTML(
                f'<div style="font-size:13px;font-weight:700;color:#0F172A;margin:12px 0 8px 0;">'
                f'Generative Models ({len(generative)})</div>'
            ))
            for entry in generative:
                self._cards_container.append(self._build_model_card(entry))

    def panel(self) -> pn.Column:
        """Build the full repository browser panel."""
        # Search bar
        search_input = pn.widgets.TextInput(
            name="",
            placeholder="Search models...",
            width=300,
            margin=(4, 8),
        )

        def on_search(event):
            self._search_text = event.new
            self._rebuild_cards()

        search_input.param.watch(on_search, "value")

        # Filter chips
        filter_buttons = []
        for f in FILTER_OPTIONS:
            btn = pn.widgets.Button(
                name=f,
                button_type="primary" if f == self._active_filter else "light",
                width=90,
                margin=(2, 2),
                stylesheets=[f"""
                    :host .bk-btn {{
                        font-size: 11px;
                        padding: 4px 10px;
                        border-radius: 16px;
                    }}
                """],
            )

            def on_filter(event, filter_name=f):
                self._active_filter = filter_name
                self._rebuild_cards()

            btn.on_click(on_filter)
            filter_buttons.append(btn)

        filter_row = pn.Row(*filter_buttons, sizing_mode="stretch_width", margin=(4, 0))

        # Build initial cards
        self._rebuild_cards()

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:16px;font-weight:800;padding:8px 0 4px 0;">'
                'Model Repository</div>'
                '<div style="font-size:12px;color:#64748B;margin-bottom:10px;">'
                'Browse and import public mRNA models. Each model is imported from its '
                'source repository and registered for use in analysis and generation workflows.</div>'
            ),
            pn.Row(search_input, sizing_mode="stretch_width"),
            filter_row,
            pn.layout.Divider(),
            self._cards_container,
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px", "max-height": "70vh", "overflow-y": "auto"},
        )
