import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import yt_dlp
import imageio_ffmpeg
import os

FORMATOS = ["mp3", "flac", "wav", "m4a", "ogg"]
CALIDADES = {"320 kbps (MP3 max)": "320", "256 kbps": "256", "192 kbps": "192", "128 kbps": "128"}

class Descargador:
    def __init__(self, root):
        self.root = root
        self.root.title("Descargador de Audio")
        self.root.geometry("600x480")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        self.carpeta_destino = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Music"))
        self.formato = tk.StringVar(value="mp3")
        self.calidad = tk.StringVar(value="320 kbps (MP3 max)")
        self.descargando = False

        self._build_ui()

    def _build_ui(self):
        estilo = ttk.Style()
        estilo.theme_use("clam")
        estilo.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        estilo.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)
        estilo.configure("TCombobox", font=("Segoe UI", 10))
        estilo.configure("TEntry", font=("Segoe UI", 10))

        titulo = tk.Label(self.root, text="Descargador de Audio", font=("Segoe UI", 16, "bold"),
                          bg="#1e1e2e", fg="#89b4fa")
        titulo.pack(pady=(20, 5))

        sub = tk.Label(self.root, text="YouTube · SoundCloud · Mixcloud · y más de 1000 sitios",
                       font=("Segoe UI", 9), bg="#1e1e2e", fg="#6c7086")
        sub.pack(pady=(0, 20))

        frame_url = tk.Frame(self.root, bg="#1e1e2e")
        frame_url.pack(fill="x", padx=30)
        tk.Label(frame_url, text="Link de la canción o playlist:", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI", 10)).pack(anchor="w")
        self.entry_url = tk.Entry(frame_url, font=("Segoe UI", 11), bg="#313244", fg="#cdd6f4",
                                  insertbackground="#cdd6f4", relief="flat", bd=6)
        self.entry_url.pack(fill="x", ipady=6, pady=(4, 0))

        frame_opciones = tk.Frame(self.root, bg="#1e1e2e")
        frame_opciones.pack(fill="x", padx=30, pady=15)

        col_formato = tk.Frame(frame_opciones, bg="#1e1e2e")
        col_formato.pack(side="left", expand=True, fill="x", padx=(0, 10))
        tk.Label(col_formato, text="Formato:", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI", 10)).pack(anchor="w")
        combo_formato = ttk.Combobox(col_formato, textvariable=self.formato,
                                     values=FORMATOS, state="readonly", width=10)
        combo_formato.pack(fill="x", pady=(4, 0))

        col_calidad = tk.Frame(frame_opciones, bg="#1e1e2e")
        col_calidad.pack(side="left", expand=True, fill="x")
        tk.Label(col_calidad, text="Calidad:", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI", 10)).pack(anchor="w")
        combo_calidad = ttk.Combobox(col_calidad, textvariable=self.calidad,
                                     values=list(CALIDADES.keys()), state="readonly", width=22)
        combo_calidad.pack(fill="x", pady=(4, 0))

        frame_carpeta = tk.Frame(self.root, bg="#1e1e2e")
        frame_carpeta.pack(fill="x", padx=30)
        tk.Label(frame_carpeta, text="Carpeta de destino:", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI", 10)).pack(anchor="w")
        fila_carpeta = tk.Frame(frame_carpeta, bg="#1e1e2e")
        fila_carpeta.pack(fill="x", pady=(4, 0))
        self.entry_carpeta = tk.Entry(fila_carpeta, textvariable=self.carpeta_destino,
                                      font=("Segoe UI", 10), bg="#313244", fg="#cdd6f4",
                                      insertbackground="#cdd6f4", relief="flat", bd=6)
        self.entry_carpeta.pack(side="left", fill="x", expand=True, ipady=5)
        tk.Button(fila_carpeta, text="...", font=("Segoe UI", 10), bg="#45475a", fg="#cdd6f4",
                  relief="flat", padx=10, command=self._elegir_carpeta).pack(side="left", padx=(6, 0))

        self.btn_descargar = tk.Button(self.root, text="Descargar",
                                       font=("Segoe UI", 12, "bold"), bg="#89b4fa", fg="#1e1e2e",
                                       relief="flat", padx=20, pady=8, cursor="hand2",
                                       command=self._iniciar_descarga)
        self.btn_descargar.pack(pady=20)

        frame_log = tk.Frame(self.root, bg="#1e1e2e")
        frame_log.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        self.txt_log = tk.Text(frame_log, font=("Consolas", 9), bg="#181825", fg="#a6e3a1",
                                relief="flat", bd=0, state="disabled", wrap="word", height=8)
        scroll = tk.Scrollbar(frame_log, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll.set)
        self.txt_log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _elegir_carpeta(self):
        carpeta = filedialog.askdirectory()
        if carpeta:
            self.carpeta_destino.set(carpeta)

    def _log(self, texto):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", texto + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _limpiar_log(self):
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

    def _iniciar_descarga(self):
        if self.descargando:
            return
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Sin link", "Pegá el link primero.")
            return
        carpeta = self.carpeta_destino.get().strip()
        if not carpeta:
            messagebox.showwarning("Sin carpeta", "Elegí una carpeta de destino.")
            return
        os.makedirs(carpeta, exist_ok=True)
        self.descargando = True
        self.btn_descargar.configure(text="Descargando...", state="disabled", bg="#6c7086")
        self._limpiar_log()
        threading.Thread(target=self._descargar, args=(url, carpeta), daemon=True).start()

    def _descargar(self, url, carpeta):
        fmt = self.formato.get()
        calidad_label = self.calidad.get()
        calidad_valor = CALIDADES.get(calidad_label, "320")
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

        def hook_progreso(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                descargado = d.get("downloaded_bytes", 0)
                velocidad = d.get("_speed_str", "").strip()
                if total:
                    pct = int(descargado / total * 100)
                    self.root.after(0, self._log, f"  {pct}%  {velocidad}")
            elif d["status"] == "finished":
                nombre = os.path.basename(d.get("filename", ""))
                self.root.after(0, self._log, f"Convirtiendo: {nombre}")

        opciones = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(carpeta, "%(title)s.%(ext)s"),
            "ffmpeg_location": ffmpeg_path,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": fmt,
                "preferredquality": calidad_valor,
            }],
            "progress_hooks": [hook_progreso],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            self.root.after(0, self._log, f"Buscando info del link...")
            with yt_dlp.YoutubeDL(opciones) as ydl:
                info = ydl.extract_info(url, download=False)
                titulo = info.get("title") or info.get("id", "desconocido")
                entradas = info.get("entries")
                if entradas:
                    self.root.after(0, self._log, f"Playlist: {len(list(entradas))} canciones — {titulo}")
                else:
                    self.root.after(0, self._log, f"Descargando: {titulo}")
                ydl.download([url])
            self.root.after(0, self._log, f"\nListo! Guardado en: {carpeta}")
            self.root.after(0, messagebox.showinfo, "Listo", f"Descarga completada.\nGuardado en: {carpeta}")
        except Exception as e:
            self.root.after(0, self._log, f"Error: {e}")
            self.root.after(0, messagebox.showerror, "Error", str(e))
        finally:
            self.descargando = False
            self.root.after(0, self.btn_descargar.configure,
                            {"text": "Descargar", "state": "normal", "bg": "#89b4fa"})


if __name__ == "__main__":
    root = tk.Tk()
    app = Descargador(root)
    root.mainloop()
