/*
  Minimal DLL for testing scripts/demo_dll_workflow.py; build yourself, e.g.:

    cl /LD demo_plugin.c /Fe:demo_plugin.dll user32.lib

  or MinGW:

    x86_64-w64-mingw32-gcc -shared -o demo_plugin.dll demo_plugin.c -Wl,--out-implib,libdemo.a

  This is not related to any third-party product; it only shows DllMain + exported Start.
*/

#include <windows.h>

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved)
{
    (void)hinstDLL;
    (void)lpvReserved;
    if (fdwReason == DLL_PROCESS_ATTACH)
        DisableThreadLibraryCalls(hinstDLL);
    return TRUE;
}

__declspec(dllexport) void __cdecl Start(void)
{
    MessageBoxA(NULL, "Start() was called.", "demo_plugin", MB_OK);
}
