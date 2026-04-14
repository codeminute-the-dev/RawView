from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

from rawview.ghidra.bridge import GhidraBridgeController

logger = logging.getLogger(__name__)


def _java_rpc_method_missing(exc: BaseException) -> bool:
    """True when Py4J reports the JVM GhidraBridge has no such method (stale rawview/java/out)."""
    s = str(exc)
    return "does not exist" in s and "Method" in s


@dataclass
class GhidraAPI:
    """Typed facade for Ghidra operations; UI and agent use this class only."""

    bridge: GhidraBridgeController

    def _invoke_json_object_rows(
        self,
        call: Callable[[Any], Any],
        *,
        empty: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        try:
            raw = self.bridge.invoke_java(call)
            data = json.loads(str(raw))
            if not isinstance(data, list):
                return empty
            return [{str(k): str(v) for k, v in row.items()} for row in data]
        except Exception as e:
            if _java_rpc_method_missing(e):
                head = str(e).split("\n", 1)[0].strip()
                logger.warning(
                    "Ghidra JVM bridge is out of date (%s). Run: python -m rawview.scripts.compile_java",
                    head[:220],
                )
                return empty
            raise

    def ping(self) -> str:
        return str(self.bridge.invoke_java(lambda ep: ep.ping()))

    def open_file(self, path: str) -> str:
        name = self.bridge.invoke_java(lambda ep: ep.openFile(path))
        return str(name)

    def run_auto_analysis(self) -> None:
        self.bridge.invoke_java(lambda ep: ep.runAutoAnalysis())

    def list_functions(self) -> list[dict[str, str]]:
        return self._invoke_json_object_rows(lambda ep: ep.listFunctionsJson(), empty=[])

    def decompile_function(self, address: str) -> str:
        return str(self.bridge.invoke_java(lambda ep: ep.decompileFunction(address)))

    def get_disassembly(self, address: str, length: int) -> str:
        return str(self.bridge.invoke_java(lambda ep: ep.getDisassembly(address, int(length))))

    def get_hex_dump(self, address: str, max_bytes: int = 4096, bytes_per_line: int = 16) -> str:
        msg = (
            "# Rebuild the Java bridge for the hex view:\n"
            "#   python -m rawview.scripts.compile_java\n"
        )
        try:
            return str(
                self.bridge.invoke_java(
                    lambda ep: ep.getHexDumpText(address, int(max_bytes), int(bytes_per_line))
                )
            )
        except Exception as e1:
            if _java_rpc_method_missing(e1):
                return msg
            try:
                return str(self.bridge.invoke_java(lambda ep: ep.getHexDumpText(address, int(max_bytes))))
            except Exception as e2:
                if _java_rpc_method_missing(e2):
                    return msg
                raise e2 from e1

    def advance_program_address(self, address: str, delta_bytes: int) -> str:
        try:
            return str(
                self.bridge.invoke_java(lambda ep: ep.advanceProgramAddress(address, int(delta_bytes)))
            ).strip()
        except Exception as e:
            if _java_rpc_method_missing(e):
                return ""
            raise

    def get_strings(self) -> list[dict[str, str]]:
        return self._invoke_json_object_rows(lambda ep: ep.getStringsJson(), empty=[])

    def get_imports(self) -> list[dict[str, str]]:
        return self._invoke_json_object_rows(lambda ep: ep.getImportsJson(), empty=[])

    def get_exports(self) -> list[dict[str, str]]:
        return self._invoke_json_object_rows(lambda ep: ep.getExportsJson(), empty=[])

    def get_symbols(self) -> list[dict[str, str]]:
        return self._invoke_json_object_rows(lambda ep: ep.getSymbolsJson(), empty=[])

    def get_entry_points(self) -> list[dict[str, str]]:
        return self._invoke_json_object_rows(lambda ep: ep.getEntryPointsJson(), empty=[])

    def get_image_base_address(self) -> str:
        return str(self.bridge.invoke_java(lambda ep: ep.getImageBaseAddress())).strip()

    def get_xrefs_to(self, address: str) -> list[dict[str, str]]:
        return self._invoke_json_object_rows(lambda ep: ep.getXrefsToJson(address), empty=[])

    def get_xrefs_from(self, address: str) -> list[dict[str, str]]:
        return self._invoke_json_object_rows(lambda ep: ep.getXrefsFromJson(address), empty=[])

    def rename_function(self, address: str, new_name: str) -> dict[str, Any]:
        raw = str(self.bridge.invoke_java(lambda ep: ep.renameFunction(address, new_name)))
        return json.loads(raw)

    def set_comment(self, address: str, text: str) -> dict[str, Any]:
        raw = str(self.bridge.invoke_java(lambda ep: ep.setComment(address, text)))
        return json.loads(raw)

    def search_bytes(self, pattern: str) -> dict[str, Any]:
        raw = str(self.bridge.invoke_java(lambda ep: ep.searchBytesJson(pattern)))
        return json.loads(raw)

    def get_data_at(self, address: str) -> dict[str, Any]:
        raw = str(self.bridge.invoke_java(lambda ep: ep.getDataAtJson(address)))
        return json.loads(raw)

    def get_control_flow_graph(self, address: str) -> dict[str, Any]:
        raw = str(self.bridge.invoke_java(lambda ep: ep.getControlFlowGraphJson(address)))
        return json.loads(raw)

    def rename_variable(self, function_address: str, old_name: str, new_name: str) -> dict[str, Any]:
        raw = str(
            self.bridge.invoke_java(
                lambda ep: ep.renameVariable(function_address, old_name, new_name)
            )
        )
        return json.loads(raw)

    def create_struct(self, address: str, struct_definition: str) -> dict[str, Any]:
        raw = str(self.bridge.invoke_java(lambda ep: ep.createStruct(address, struct_definition)))
        return json.loads(raw)

    def set_function_signature(self, address: str, signature: str) -> dict[str, Any]:
        raw = str(self.bridge.invoke_java(lambda ep: ep.setFunctionSignature(address, signature)))
        return json.loads(raw)

    def close_all(self) -> None:
        self.bridge.invoke_java(lambda ep: ep.closeAll())

    def flush_program_to_disk(self) -> None:
        self.bridge.invoke_java(lambda ep: ep.flushProgramToDisk())

    def get_re_session_meta(self) -> dict[str, str]:
        raw = str(self.bridge.invoke_java(lambda ep: ep.getReSessionMetaJson()))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}

    def open_saved_project(
        self,
        projects_parent: str,
        project_folder: str,
        program_folder: str,
        program_domain: str,
    ) -> str:
        return str(
            self.bridge.invoke_java(
                lambda ep: ep.openSavedProject(
                    projects_parent,
                    project_folder,
                    program_folder,
                    program_domain,
                )
            )
        )
