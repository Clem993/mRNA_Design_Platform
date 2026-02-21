"""
Parts Workshop — mRNA assembly from parts library.

Users select multiple parts from each category (5'UTR, Kozak, CDS, 3'UTR, PolyA)
and generate all combinatorial assemblies. Make mode only.
"""
from __future__ import annotations

import itertools
import logging
from typing import TYPE_CHECKING, Dict, List, Optional

import panel as pn
import param

from core.models.sequence import mRNASequence

if TYPE_CHECKING:
    from ui.state import AppState
    from core.models.parts import SequencePart

logger = logging.getLogger(__name__)


class PlasmidView(param.Parameterized):
    """Parts Workshop panel for mRNA assembly."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state

        # Selected parts
        self._selected_5utr: Optional[SequencePart] = None
        self._selected_kozak: Optional[SequencePart] = None
        self._selected_cds: Optional[SequencePart] = None
        self._selected_3utr: Optional[SequencePart] = None
        self._selected_polya: Optional[SequencePart] = None

        # UI widgets
        self._utr5_select: Optional[pn.widgets.Select] = None
        self._kozak_select: Optional[pn.widgets.Select] = None
        self._cds_select: Optional[pn.widgets.Select] = None
        self._utr3_select: Optional[pn.widgets.Select] = None
        self._polya_select: Optional[pn.widgets.Select] = None

        self._result_pane = pn.pane.HTML("")
        self._sequence_name = pn.widgets.TextInput(
            name="Sequence Name",
            placeholder="e.g., custom_mrna_001",
            value="",
            width=300,
        )

    def _build_part_selector(
        self, part_type: str, label: str, color: str
    ) -> pn.Column:
        """Build a multi-select widget for a specific part type."""
        parts = self._state.parts_by_type(part_type)

        if not parts:
            options_list = []
            disabled = True
        else:
            options_list = parts
            disabled = False

        selector = pn.widgets.MultiSelect(
            name=label,
            options={p.name: p for p in options_list},
            value=[],
            size=5,
            width=300,
            disabled=disabled,
        )

        # Store reference
        if part_type == "5_utr":
            self._utr5_select = selector
        elif part_type == "kozak":
            self._kozak_select = selector
        elif part_type == "cds":
            self._cds_select = selector
        elif part_type == "3_utr":
            self._utr3_select = selector
        elif part_type == "polya":
            self._polya_select = selector

        # Info display
        @param.depends(selector.param.value)
        def part_info(selected_parts):
            if not selected_parts:
                return pn.pane.HTML(
                    f'<div style="font-size:11px;color:#94A3B8;margin-top:4px;">'\
                    f'No parts selected</div>'
                )
            return pn.pane.HTML(
                f'<div style="font-size:11px;color:#64748B;margin-top:4px;">'\
                f'{len(selected_parts)} part(s) selected</div>'
            )

        return pn.Column(
            pn.pane.HTML(
                f'<div style="font-weight:700;font-size:13px;color:{color};'\
                f'margin-bottom:4px;">{label} (multi-select)</div>'
            ),
            selector,
            pn.panel(part_info),
            sizing_mode="stretch_width",
            styles={"background": "#F8FAFC", "padding": "12px", "border-radius": "6px"},
        )

    @param.depends("_state.parts_library")
    def panel(self) -> pn.Column:
        """Main panel layout."""

        # Header
        header = pn.pane.HTML(
            '<div style="font-size:16px;font-weight:800;padding:8px 0 4px 0;">'\
            'Parts Workshop</div>'\
            '<div style="font-size:12px;color:#64748B;margin-bottom:16px;">'\
            f'Select parts from the library ({len(self._state.parts_library)} parts available) '\
            'to assemble a new mRNA sequence.</div>'
        )

        # Part selectors in a grid
        selectors = pn.GridBox(
            self._build_part_selector("5_utr", "5' UTR", "#4A90D9"),
            self._build_part_selector("kozak", "Kozak", "#F5A623"),
            self._build_part_selector("cds", "CDS", "#7ED321"),
            self._build_part_selector("3_utr", "3' UTR", "#9B59B6"),
            self._build_part_selector("polya", "Poly-A", "#E74C3C"),
            ncols=3,
            sizing_mode="stretch_width",
        )

        # Assembly controls
        assemble_btn = pn.widgets.Button(
            name="Preview Combinations",
            button_type="primary",
            width=180,
            margin=(12, 4),
        )
        assemble_btn.on_click(self._on_assemble)

        add_to_worklist_btn = pn.widgets.Button(
            name="Generate & Add to Worklist",
            button_type="success",
            width=220,
            margin=(12, 4),
            visible=False,
        )
        self._add_to_worklist_btn = add_to_worklist_btn
        add_to_worklist_btn.on_click(self._on_add_to_worklist)

        self._combo_count_pane = pn.pane.HTML("", margin=(12, 4))

        controls = pn.Row(
            self._combo_count_pane,
            pn.layout.HSpacer(),
            assemble_btn,
            add_to_worklist_btn,
            sizing_mode="stretch_width",
        )

        # Result display
        result_section = pn.Column(
            pn.layout.Divider(),
            self._result_pane,
            sizing_mode="stretch_width",
        )

        return pn.Column(
            header,
            selectors,
            controls,
            result_section,
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )

    def _on_assemble(self, event: object) -> None:
        """Preview combinatorial assemblies."""
        logger.info("Preview combinations button clicked")

        # Collect selected parts for each category
        part_groups = []
        part_labels = []

        if self._utr5_select and self._utr5_select.value:
            part_groups.append([("5' UTR", p) for p in self._utr5_select.value])
            part_labels.append("5'UTR")
        if self._kozak_select and self._kozak_select.value:
            part_groups.append([("Kozak", p) for p in self._kozak_select.value])
            part_labels.append("Kozak")
        if self._cds_select and self._cds_select.value:
            part_groups.append([("CDS", p) for p in self._cds_select.value])
            part_labels.append("CDS")
        if self._utr3_select and self._utr3_select.value:
            part_groups.append([("3' UTR", p) for p in self._utr3_select.value])
            part_labels.append("3'UTR")
        if self._polya_select and self._polya_select.value:
            part_groups.append([("Poly-A", p) for p in self._polya_select.value])
            part_labels.append("PolyA")

        if not part_groups:
            self._result_pane.object = (
                '<div style="color:#E74C3C;padding:12px;">'\
                'Please select at least one part to assemble.</div>'
            )
            self._add_to_worklist_btn.visible = False
            self._combo_count_pane.object = ""
            return

        # Calculate number of combinations
        combo_count = 1
        for group in part_groups:
            combo_count *= len(group)

        logger.info(f"Generating {combo_count} combinatorial assemblies")

        # Show summary
        selection_summary = " × ".join([
            f"{len(group)} {part_labels[i]}"
            for i, group in enumerate(part_groups)
        ])

        # Show first few combinations as preview
        combinations = list(itertools.product(*part_groups))[:5]
        preview_html = ""
        for i, combo in enumerate(combinations, 1):
            combo_parts = [f"{label}: {part.name}" for label, part in combo]
            preview_html += f'<div style="margin:4px 0;font-size:11px;">'\
                           f'<strong>Example {i}:</strong> {" + ".join(combo_parts)}</div>'

        if combo_count > 5:
            preview_html += f'<div style="margin-top:8px;font-style:italic;color:#64748B;font-size:11px;">'\
                           f'... and {combo_count - 5} more combinations</div>'

        self._combo_count_pane.object = (
            f'<div style="font-size:13px;font-weight:700;color:#6366F1;">'\
            f'{combo_count} sequences will be generated</div>'\
            f'<div style="font-size:11px;color:#64748B;">({selection_summary})</div>'
        )

        self._result_pane.object = (
            f'<div style="background:#EEF2FF;border:1px solid #6366F1;border-radius:6px;'\
            f'padding:16px;margin-top:12px;">'\
            f'<div style="font-weight:700;color:#4338CA;margin-bottom:8px;">'\
            f'✓ Combination Preview ({combo_count} sequences)</div>'\
            f'<div style="font-size:12px;color:#312E81;">'\
            f'{preview_html}'\
            f'</div></div>'
        )

        self._add_to_worklist_btn.visible = True
        logger.info(f"Preview generated for {combo_count} combinations")

    def _on_add_to_worklist(self, event: object) -> None:
        """Generate all combinatorial mRNASequences and add to worklist."""
        logger.info("Generate & add to worklist button clicked")

        # Collect selected parts for each category
        utr5_parts = list(self._utr5_select.value) if self._utr5_select and self._utr5_select.value else [None]
        kozak_parts = list(self._kozak_select.value) if self._kozak_select and self._kozak_select.value else [None]
        cds_parts = list(self._cds_select.value) if self._cds_select and self._cds_select.value else [None]
        utr3_parts = list(self._utr3_select.value) if self._utr3_select and self._utr3_select.value else [None]
        polya_parts = list(self._polya_select.value) if self._polya_select and self._polya_select.value else [None]

        # Generate all combinations
        combinations = itertools.product(
            utr5_parts,
            kozak_parts,
            cds_parts,
            utr3_parts,
            polya_parts
        )

        sequences_added = 0
        for i, (utr5, kozak, cds, utr3, polya) in enumerate(combinations, 1):
            # Build name from parts
            name_parts = []
            if utr5:
                name_parts.append(utr5.name.split("_")[0])
            if kozak:
                name_parts.append(kozak.name.split("_")[0])
            if cds:
                name_parts.append(cds.name.split("_")[0])
            if utr3:
                name_parts.append(utr3.name.split("_")[0])
            if polya:
                name_parts.append(polya.name.split("_")[0])

            seq_name = "_".join(name_parts) + f"_v{i}"

            # Create mRNASequence
            seq = mRNASequence(
                name=seq_name,
                source="local",
                five_prime_utr=utr5.sequence if utr5 else None,
                kozak=kozak.sequence if kozak else None,
                cds=cds.sequence if cds else None,
                three_prime_utr=utr3.sequence if utr3 else None,
                poly_a=polya.sequence if polya else None,
            )

            # Add to worklist
            self._state.worklist.add(seq, origin="generated")
            sequences_added += 1

        self._state.param.trigger("worklist")

        logger.info(f"Added {sequences_added} assembled sequences to worklist")

        # Show success message
        self._state.set_status(f"Generated and added {sequences_added} sequences to worklist")

        # Reset form
        self._result_pane.object = (
            f'<div style="color:#10B981;padding:12px;">'\
            f'✓ Generated and added {sequences_added} sequences to worklist!<br>'\
            f'You can now find them in the Worklist tab.</div>'
        )
        self._add_to_worklist_btn.visible = False
        self._combo_count_pane.object = ""
