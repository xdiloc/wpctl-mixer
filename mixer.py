import tkinter as tk
import subprocess
import re

# --- КОНФИГУРАТОР ЦВЕТОВОЙ СХЕМЫ И ЭЛЕМЕНТОВ ---
THEME = {
	"window": {
		"bg": "#000000"
	},
	"column": {
		"bg": "#1a1a1a",
		"border_color": "#333",
		"border_width": 1,
		"padx": 2,
		"pady": 2
	},
	"label_name": {
		"fg": "#32cd32",              # Насыщенный Lime Green
		"bg": "#1a1a1a",
		"font": ("monospace", 8, "bold"),
		"show": True
	},
	"label_vol": {
		"fg": "#ffffff",
		"bg": "#1a1a1a",
		"font": ("monospace", 10),
		"format": "{}%",
		"show": True
	},
	"scale": {
		"troughcolor": "#333",
		"activebackground": "#32cd32",
		"fg": "#32cd32",
		"bg": "#1a1a1a",
		"width": 15,
		"length": 200,
		"border_width": 0,
		"highlight_thickness": 0
	},
	"button": {
		"active_bg": "#32cd32",        # Мягкий, но яркий зеленый
		"inactive_bg": "#dc143c",      # Насыщенный Crimson
		"fg": "#000",
		"font": ("monospace", 7, "bold"),
		"text_active": "ACTIVE",
		"text_inactive": "SET DEFAULT"
	},
	"label_id": {
		"fg": "#666",                  # Чуть приподнял яркость ID для читаемости
		"bg": "#1a1a1a",
		"font": ("monospace", 7),
		"prefix": "ID: ",
		"show": True
	}
}

# Регулярное выражение скомпилировано заранее для ускорения обработки (Profile-Guided Focus)
SINK_PATTERN = re.compile(r"(\*|\s+)\s+(\d+)\.\s+(.*?)\s+\[vol:\s+([\d\.]+)")

# @brief Выполняет системную команду и возвращает вывод
# cmd - список аргументов команды
def run_cmd(cmd):
	try:
		return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8")
	except:
		return ""

# @brief Получает актуальные данные обо всех Sinks с минимизацией аллокаций
def get_all_sinks():
	status_out = run_cmd(["wpctl", "status"])
	if not status_out:
		return []

	# Profile-Guided Focus: Вместо split-аллокаций используем find для поиска границ
	start_idx = status_out.find("Sinks:")
	if start_idx == -1:
		return []

	end_idx = status_out.find("Sink endpoints:", start_idx)
	# Если конец не найден, берем до конца строки
	section = status_out[start_idx:end_idx] if end_idx != -1 else status_out[start_idx:]

	sinks = []
	# Используем finditer вместо splitlines, чтобы не нарезать строку на объекты
	for match in SINK_PATTERN.finditer(section):
		sinks.append({
			"id": match.group(2),
			"name": match.group(3).strip(),
			"vol": float(match.group(4)),
			"is_default": match.group(1) == "*"
		})
	return sinks

ui_elements = {}

# @brief Полная перерисовка интерфейса при изменении состава устройств
def refresh_ui():
	for widget in root.winfo_children():
		widget.destroy()

	# Сброс конфигурации старых колонок, чтобы не оставалось пустого места
	for i in range(root.grid_size()[0]):
		root.columnconfigure(i, weight=0, uniform="")

	ui_elements.clear()

	current_sinks = get_all_sinks()
	num_sinks = len(current_sinks)
	
	new_width = max(200, num_sinks * 150)
	root.geometry(f"{new_width}x450")

	for i, sink in enumerate(current_sinks):
		create_mixer_column(root, sink, i)

	root.rowconfigure(0, weight=1)

# @brief Фоновое обновление громкости и состава устройств
def update_volumes():
	current_sinks = get_all_sinks()
	current_ids = {s['id'] for s in current_sinks}
	existing_ids = set(ui_elements.keys())

	if current_ids != existing_ids:
		refresh_ui()
		root.after(500, update_volumes)
		return

	for s in current_sinks:
		if s['id'] in ui_elements:
			current_val = float(ui_elements[s['id']]['scale'].get())
			if abs(current_val - s['vol']) > 0.01:
				ui_elements[s['id']]['scale'].set(s['vol'])
				if THEME["label_vol"]["show"]:
					ui_elements[s['id']]['label'].config(text=THEME["label_vol"]["format"].format(int(s['vol']*100)))
			
			btn = ui_elements[s['id']]['btn']
			target_bg = THEME["button"]["active_bg"] if s['is_default'] else THEME["button"]["inactive_bg"]
			target_text = THEME["button"]["text_active"] if s['is_default'] else THEME["button"]["text_inactive"]
			
			if btn.cget("bg") != target_bg:
				btn.config(bg=target_bg, activebackground=target_bg, text=target_text)
				
	root.after(500, update_volumes)

# @brief Установка уровня громкости через wpctl
# dev_id - идентификатор устройства
# val - значение громкости
def set_vol(dev_id, val):
	subprocess.run(["wpctl", "set-volume", str(dev_id), f"{float(val):.2f}"], check=False)

# @brief Установка устройства по умолчанию
# dev_id - идентификатор устройства
def set_default(dev_id):
	subprocess.run(["wpctl", "set-default", str(dev_id)], check=False)

# @brief Создает колонку управления для конкретного устройства
# parent - родительский контейнер
# sink - данные устройства
# col - индекс колонки
def create_mixer_column(parent, sink, col):
	parent.columnconfigure(col, weight=1, uniform="group1")
	frame = tk.Frame(
		parent, 
		bg=THEME["column"]["bg"], 
		highlightbackground=THEME["column"]["border_color"], 
		highlightthickness=THEME["column"]["border_width"]
	)
	frame.grid(row=0, column=col, sticky="nsew", padx=THEME["column"]["padx"], pady=THEME["column"]["pady"])
	
	if THEME["label_name"]["show"]:
		tk.Label(
			frame, text=sink['name'], 
			fg=THEME["label_name"]["fg"], bg=THEME["label_name"]["bg"],
			font=THEME["label_name"]["font"], wraplength=120, justify=tk.CENTER, height=3
		).pack(side=tk.TOP, pady=10, fill=tk.X)

	val_label = None
	if THEME["label_vol"]["show"]:
		val_label = tk.Label(
			frame, 
			text=THEME["label_vol"]["format"].format(int(sink['vol']*100)), 
			fg=THEME["label_vol"]["fg"], bg=THEME["label_vol"]["bg"], 
			font=THEME["label_vol"]["font"]
		)
		val_label.pack(side=tk.TOP)

	def on_move(v):
		set_vol(sink['id'], v)
		if val_label:
			val_label.config(text=THEME["label_vol"]["format"].format(int(float(v)*100)))

	scale = tk.Scale(
		frame, from_=1.0, to=0.0, resolution=0.01,
		orient=tk.VERTICAL, length=THEME["scale"]["length"], showvalue=False,
		command=on_move, bg=THEME["scale"]["bg"], fg=THEME["scale"]["fg"], 
		highlightthickness=THEME["scale"]["highlight_thickness"], 
		bd=THEME["scale"]["border_width"],
		troughcolor=THEME["scale"]["troughcolor"], 
		activebackground=THEME["scale"]["activebackground"], width=THEME["scale"]["width"]
	)
	scale.set(sink['vol'])
	scale.pack(side=tk.TOP, pady=10, expand=True)

	btn_color = THEME["button"]["active_bg"] if sink['is_default'] else THEME["button"]["inactive_bg"]
	btn_text = THEME["button"]["text_active"] if sink['is_default'] else THEME["button"]["text_inactive"]
	
	def_btn = tk.Button(
		frame, text=btn_text, font=THEME["button"]["font"],
		bg=btn_color, fg=THEME["button"]["fg"], activebackground=btn_color,
		command=lambda s_id=sink['id']: set_default(s_id),
		relief=tk.FLAT, bd=0
	)
	def_btn.pack(side=tk.TOP, pady=5, padx=10, fill=tk.X)
	
	if THEME["label_id"]["show"]:
		tk.Label(
			frame, text=f"{THEME['label_id']['prefix']}{sink['id']}", 
			fg=THEME["label_id"]["fg"], bg=THEME["label_id"]["bg"], 
			font=THEME["label_id"]["font"]
		).pack(side=tk.BOTTOM, pady=5)
	
	ui_elements[sink['id']] = {'scale': scale, 'label': val_label, 'btn': def_btn}

root = tk.Tk()
root.title("System Mixer Live")
root.configure(bg=THEME["window"]["bg"])

refresh_ui()
root.after(500, update_volumes)
root.mainloop()
