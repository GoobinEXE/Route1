from services.file_picker import qt_filters_to_webview


def test_qt_filters_to_webview_normalizes_patterns():
    out = qt_filters_to_webview(
        (
            "ROMs (*.nds *.dsi)",
            "Portáteis (*.gba;*.gbc)",
            "Todos os ficheiros (*.*)",
        )
    )
    assert out == (
        "ROMs (*.nds;*.dsi)",
        "Portáteis (*.gba;*.gbc)",
        "Todos os ficheiros (*.*)",
    )


def test_qt_filters_to_webview_defaults_when_empty():
    out = qt_filters_to_webview((None, "", "   "))
    assert out == ("Todos os ficheiros (*.*)",)
