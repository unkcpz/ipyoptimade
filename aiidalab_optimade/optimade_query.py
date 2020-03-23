from typing import Union
from simplejson import JSONDecodeError
import requests
import traitlets
import ipywidgets as ipw

from aiidalab_optimade.converters import Structure
from aiidalab_optimade.exceptions import InputError, BadResource
from aiidalab_optimade.subwidgets import (
    ProvidersImplementations,
    StructureDropdown,
    FilterInputs,
    ResultsPageChooser,
)
from aiidalab_optimade.utils import validate_api_version, perform_optimade_query


DEFAULT_FILTER_VALUE = (
    'chemical_formula_descriptive CONTAINS "Al" OR (chemical_formula_anonymous = "AB" AND '
    'elements HAS ALL "Si","Al","O")'
)


class OptimadeQueryWidget(ipw.VBox):  # pylint: disable=too-many-instance-attributes
    """Structure search and import widget for OPTiMaDe

    NOTE: Only supports offset-pagination at the moment.
    """

    structure = traitlets.Instance(Structure, allow_none=True)
    database = traitlets.Tuple(traitlets.Unicode(), traitlets.Dict(allow_none=True))

    def __init__(
        self,
        debug: bool = False,
        embedded: bool = False,
        result_limit: int = None,
        **kwargs,
    ):
        self.debug = debug
        self.embedded = embedded
        self.page_limit = result_limit if result_limit else 10
        self.offset = 0

        self.base_url = ProvidersImplementations(
            include_summary=not self.embedded, debug=self.debug
        )
        self.base_url.observe(self._on_database_select, names="database")

        self.filter_header = ipw.HTML("<br><h4>Apply filters</h4>")
        self.filters = FilterInputs()
        self.filters.freeze()
        self.filters.on_submit(self.retrieve_data)
        self.query_button = ipw.Button(
            description="Search",
            button_style="primary",
            icon="search",
            disabled=True,
            tooltip="Search - No database chosen",
        )
        self.query_button.on_click(self.retrieve_data)

        self.structures_header = ipw.HTML("<br><h4>Results</h4>")
        self.structure_drop = StructureDropdown(disabled=True)
        self.structure_drop.observe(self._on_structure_select, names="value")
        self.error_or_status_messages = ipw.HTML("")

        self.structure_page_chooser = ResultsPageChooser(self.page_limit)
        self.structure_page_chooser.observe(
            self._get_more_results, names=["page_offset", "page_link"]
        )

        super().__init__(
            children=[
                self.base_url,
                self.filter_header,
                self.filters,
                self.query_button,
                self.structures_header,
                self.structure_drop,
                self.error_or_status_messages,
                self.structure_page_chooser,
            ],
            layout=ipw.Layout(width="100%"),
            **kwargs,
        )

    def _on_database_select(self, change):
        """Load chosen database"""
        self.database = change["new"]
        if self.database[1] is None or self.database[1].get("base_url", None) is None:
            self.query_button.disabled = True
            self.query_button.tooltip = "Search - No database chosen"
            self.filters.freeze()
        else:
            self.query_button.disabled = False
            self.query_button.tooltip = "Search"
            self.filters.unfreeze()
        self.structure_drop.reset()

    def _on_structure_select(self, change):
        """Update structure trait with chosen structure dropdown value"""
        chosen_structure = change["new"]
        if chosen_structure is None:
            self.structure = None
            with self.hold_trait_notifications():
                self.structure_drop.index = 0
        else:
            self.structure = chosen_structure["structure"]

    def _get_more_results(self, change):
        """Query for more results according to page_offset"""
        offset_or_link: Union[int, str] = change["new"]
        if isinstance(offset_or_link, int):
            self.offset = offset_or_link
            offset_or_link = None

        try:
            # Freeze and disable list of structures in dropdown widget
            # We don't want changes leading to weird things happening prior to the query ending
            self.freeze()

            # Update button text and icon
            self.query_button.description = "Updating ... "
            self.query_button.icon = "cog"
            self.query_button.tooltip = "Please wait ..."

            # Query database
            response = self._query(offset_or_link)
            if self.handle_errors(response):
                return

            # Update list of structures in dropdown widget
            self._update_structures(response["data"])

            # Update pageing
            self.structure_page_chooser.set_pagination_data(
                links_to_page=response.get("links", {}),
            )

        finally:
            self.query_button.description = "Search"
            self.query_button.icon = "search"
            self.query_button.tooltip = "Search"
            self.unfreeze()

    def freeze(self):
        """Disable widget"""
        self.query_button.disabled = True
        self.filters.freeze()
        self.base_url.freeze()
        self.structure_drop.freeze()
        self.structure_page_chooser.freeze()

    def unfreeze(self):
        """Activate widget (in its current state)"""
        self.query_button.disabled = False
        self.filters.unfreeze()
        self.base_url.unfreeze()
        self.structure_drop.unfreeze()
        self.structure_page_chooser.unfreeze()

    def reset(self):
        """Reset widget"""
        with self.hold_trait_notifications():
            self.query_button.disabled = False
            self.query_button.tooltip = "Search - No database chosen"
            self.filters.reset()
            self.base_url.reset()
            self.structure_drop.reset()
            self.structure_page_chooser.reset()

    def _query(self, link: str = None) -> dict:
        """Query helper function"""

        # If a complete link is provided, use it straight up
        if link is not None:
            try:
                response = requests.get(link).json()
            except JSONDecodeError:
                response = {"errors": {}}
            return response

        # Avoid structures that cannot be converted to an ASE.Atoms instance
        add_to_filter = 'NOT structure_features HAS ANY "disorder","unknown_positions"'

        filter_ = self.filters.collect_value()
        filter_ = (
            "( {} ) AND ( {} )".format(filter_, add_to_filter)
            if filter_
            else add_to_filter
        )
        if self.debug:
            print(filter_)

        # OPTiMaDe queries
        queries = {
            "base_url": self.database[1]["base_url"],
            "filter_": filter_,
            "format_": "json",
            "email": None,
            "fields": None,
            "limit": self.page_limit,
            "offset": self.offset,
        }

        return perform_optimade_query(**queries)

    def handle_errors(self, response: dict) -> bool:
        """Handle any errors"""
        if "data" not in response and "errors" not in response:
            raise InputError(f"No data and no errors reported in response: {response}")

        if "errors" in response:
            if "data" in response:
                self.error_or_status_messages.value = (
                    '<font color="red">Error(s) during querying,</font> but '
                    f"<strong>{len(response['data'])}</strong> structures found."
                )
            else:
                self.error_or_status_messages.value = (
                    '<font color="red">Error during querying, '
                    "please try again later.</font>"
                )
            if self.debug:
                import json

                print(json.dumps(response, indent=2))
            return True

        return False

    def _update_structures(self, data: list):
        """Update structures dropdown from response data"""
        structures = []

        for entry in data:
            structure = Structure(entry)

            formula = structure.attributes.chemical_formula_descriptive
            if formula is None:
                formula = structure.attributes.chemical_formula_reduced
            if formula is None:
                formula = structure.attributes.chemical_formula_anonymous
            if formula is None:
                formula = structure.attributes.chemical_formula_hill
            if formula is None:
                raise BadResource(
                    resource=structure,
                    fields=[
                        "chemical_formula_descriptive",
                        "chemical_formula_reduced",
                        "chemical_formula_anonymous",
                        "chemical_formula_hill",
                    ],
                    msg="At least one of the following chemical formula fields "
                    "should have a valid value",
                )

            entry_name = f"{formula} (id={structure.id})"
            structures.append((entry_name, {"structure": structure}))

        # Update list of structures in dropdown widget
        self.structure_drop.set_options(structures)

    def retrieve_data(self, _):
        """Perform query and retrieve data"""
        try:
            # Freeze and disable list of structures in dropdown widget
            # We don't want changes leading to weird things happening prior to the query ending
            self.freeze()

            # Reset the error or status message
            if self.error_or_status_messages.value:
                self.error_or_status_messages.value = ""

            # Update button text and icon
            self.query_button.description = "Querying ... "
            self.query_button.icon = "cog"
            self.query_button.tooltip = "Please wait ..."

            # Query database
            response = self._query()
            if self.handle_errors(response):
                return

            # Check implementation API version
            validate_api_version(response.get("meta", {}).get("api_version", ""))

            # Update list of structures in dropdown widget
            self._update_structures(response["data"])

            # Update pageing
            self.structure_page_chooser.set_pagination_data(
                data_returned=response.get("meta", {}).get("data_returned", 0),
                links_to_page=response.get("links", {}),
                reset_cache=True,
            )

        finally:
            self.query_button.description = "Search"
            self.query_button.icon = "search"
            self.query_button.tooltip = "Search"
            self.unfreeze()
