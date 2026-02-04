# Opis

**Lekki, wydajny manager lokalnych plików wideo z interfejsem webowym, integracją TMDB i inteligentnym streamingiem.**

Projekt powstał z potrzeby zarządzania lokalną biblioteką filmów i seriali (w tym anime), która wykracza poza możliwości standardowych odtwarzaczy przeglądarkowych. Aplikacja skanuje dysk, pobiera metadane, organizuje pliki w bazę SQL i pozwala na ich odtwarzanie bezpośrednio w przeglądarce, omijając problemy z kodekami (MKV/HEVC).

## ✨ Główne funkcje

### 🗂️ Zarządzanie Biblioteką
*   **Integracja z TMDB:** Automatyczne pobieranie okładek, tytułów i opisów dla Filmów i Seriali.
*   **Własne Serie (Custom):** Możliwość dodawania treści spoza baz (np. serie z YouTube, prywatne nagrania) z własnymi okładkami.
*   **Inteligentne Skanowanie:** Regexy wykrywające numery sezonów i odcinków (np. `S02E05`, `2x05`).
*   **Masowa Edycja:** Narzędzia do szybkiego przypisywania sezonów i numeracji dla wielu plików jednocześnie.

### 🚀 Advanced Streaming & Playback
*   **Direct Stream (Range Requests):** Obsługa natywnego przewijania i buforowania dla formatów wspieranych przez przeglądarkę.
*   **Server-Side Remux (FFmpeg):** Rozwiązanie problemu "czarnego ekranu" w przeglądarkach dla plików **MKV/HEVC**.
    *   Silnik w locie zmienia kontener na MP4 (`-c:v copy`).
    *   **Zerowe użycie CPU** dla wideo (kopiowanie strumienia).
    *   Konwersja audio do AAC w czasie rzeczywistym.
    *   Umożliwia wykorzystanie akceleracji sprzętowej GPU w przeglądarce.
*   **System Integration:** Opcja "Otwórz w VLC/Systemie" jednym kliknięciem dla plików, których przeglądarka absolutnie nie obsługuje.

### 💾 Baza Danych
*   Oparta na **SQLite**.
*   Przechowuje ścieżki, metadane i status obejrzenia.
*   Działa lokalnie – pełna prywatność, brak wysyłania danych o plikach do chmury.

## 🛠️ Technologie

*   **Backend:** Python 3, Flask
*   **Baza danych:** SQLite3
*   **Frontend:** HTML5, Bootstrap 5, Vanilla JS
*   **Media Engine:** FFmpeg (wymagany w systemie)
*   **API:** The Movie Database (TMDB) API

## ⚙️ Instalacja i Uruchomienie

1.  **Sklonuj repozytorium:**
    ```bash
    git clone https://github.com/zbirow/Lokalna-Baza-Danych-Film-w-i-Seriali.git
    cd media-manager
    ```

2.  **Zainstaluj zależności:**
    ```bash
    pip install flask requests
    ```

3.  **Wymagania systemowe:**
    *   Zainstalowany **FFmpeg** dodany do zmiennych środowiskowych (PATH), aby działał Remuxer.

4.  **Konfiguracja:**
    *   W pliku `app.py` uzupełnij swój klucz API:
    ```python
    TMDB_API_KEY = "TWÓJ_KLUCZ_TMDB"
    ```

5.  **Uruchomienie:**
    ```bash
    python app.py
    ```
    Aplikacja dostępna pod adresem: `http://127.0.0.1:5000`

## 📖 Jak używać?

1.  Wejdź w zakładkę **Manager**.
2.  Wybierz folder z filmami na dysku.
3.  Zaznacz pliki i wyszukaj je w TMDB (lub dodaj jako Własną Serię).
4.  Wróć do **Biblioteki** i oglądaj.
    *   Jeśli plik jest MKV, player automatycznie spróbuje go zremuxować w locie, aby działał płynnie w Chrome/Edge.
