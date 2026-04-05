import tkinter as tk
from tkinter import messagebox
from meilin_map import MeilinMap
from solver import MerlinALLRouter, MerlinMasterRouter, SolverConfigError

class MerlinWeightedPathFinder:
    def __init__(self, root, half_flag="blue", coordinates=None, heights=None):
        self.root = root
        self.root.title("ROBOCON 2026 - 梅林带权图智能寻路 (Dijkstra + TSP)")
        self.root.geometry("650x850")
        
        self.STATES = ["EMPTY", "R2", "R1", "FAKE"]
        self.COLORS = {"EMPTY": "#f0f0f0", "R2": "#a8e6cf", "R1": "#ffb347", "FAKE": "#dcedc1"}

        # self.route_solver = MerlinALLRouter(required_counts=self.required_counts)
        self.route_solver = MerlinMasterRouter()
        self.map_model = MeilinMap(
            half_flag=half_flag,
            coordinates=coordinates,
            heights=heights,
        )
        self.LABELS = {
            "EMPTY": "",
            "R2": f"R2目标 (代价{self.map_model.normal_cost})",
            "R1": f"R1阻挡 (代价{self.map_model.r1_penalty})",
            "FAKE": "假KFS (死路)",
        }
        
        self.create_widgets()

    def create_widgets(self):
        info_frame = tk.Frame(self.root)
        info_frame.pack(pady=10)
        tk.Label(info_frame, text=f"空地/R2 代价={self.map_model.normal_cost}步 | R1 代价={self.map_model.r1_penalty} (需等待队友) | 假KFS=死路", font=("Arial", 11, "bold")).pack()

        self.canvas = tk.Canvas(self.root, width=400, height=530, bg="white", highlightthickness=2, highlightbackground="black")
        self.canvas.pack(pady=10)
        
        self.rects = {}
        self.texts = {}
        self.path_elements = []
        
        for i in range(1, 13):
            row, col = (i - 1) // 3, (i - 1) % 3
            x1, y1 = 20 + col * 120, 20 + row * 120
            x2, y2 = x1 + 120, y1 + 120
            
            rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, fill=self.COLORS["EMPTY"], width=2)
            num_id = self.canvas.create_text((x1+x2)/2, (y1+y2)/2 - 20, text=f"{i}", font=("Arial", 24, "bold"), fill="#cccccc")
            state_id = self.canvas.create_text((x1+x2)/2, (y1+y2)/2 + 20, text="", font=("Arial", 10, "bold"))
            
            self.rects[i] = rect_id
            self.texts[i] = state_id
            
            self.canvas.tag_bind(rect_id, "<Button-1>", lambda e, cid=i: self.cycle_state(cid))
            self.canvas.tag_bind(num_id, "<Button-1>", lambda e, cid=i: self.cycle_state(cid))
            self.canvas.tag_bind(state_id, "<Button-1>", lambda e, cid=i: self.cycle_state(cid))

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="清空网格", command=self.reset_grid, width=10).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="计算最小代价路径", command=self.calculate_path, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), width=15).pack(side=tk.LEFT, padx=10)

        self.count_label = tk.Label(self.root, font=("Arial", 10))
        self.count_label.pack(pady=4)
        self.update_counts()
        
        self.result_text = tk.StringVar()
        self.result_text.set("等待计算...")
        tk.Label(self.root, textvariable=self.result_text, font=("Arial", 11), justify=tk.LEFT).pack(pady=10)

    def cycle_state(self, cell_id):
        curr_state = self.map_model.piles[cell_id].block_type
        idx = (self.STATES.index(curr_state) + 1) % len(self.STATES)
        new_state = self.STATES[idx]
        self.map_model._set_block_type_by_id(cell_id, new_state)
        self.canvas.itemconfig(self.rects[cell_id], fill=self.COLORS[new_state])
        self.canvas.itemconfig(self.texts[cell_id], text=self.LABELS[new_state])
        self.update_counts()
        self.clear_path()

    def update_counts(self):
        counts = self.map_model.count_types()
        self.count_label.config(
            text=f"当前数量: R2({counts['R2']}), R1({counts['R1']}), 假KFS({counts['FAKE']})"
        )

    def clear_path(self):
        for item in self.path_elements: self.canvas.delete(item)
        self.path_elements.clear()

    def reset_grid(self):
        for i in range(1, 13):
            self.map_model._set_block_type_by_id(i, "EMPTY")
            self.canvas.itemconfig(self.rects[i], fill=self.COLORS["EMPTY"])
            self.canvas.itemconfig(self.texts[i], text="")
        self.update_counts()
        self.clear_path()

    def calculate_path(self):
        self.clear_path()
        try:

            # path, total_cost = self.route_solver._solve_weighted_route(self.map_model.piles)
            path, total_cost = self.route_solver._solve_two_phase_route(self.map_model.piles)

        except SolverConfigError as exc:
            messagebox.showerror("配置错误", str(exc))
            return

        if path:
            log = "已完成全局最优搜索。\n"

            log += f"全局最优总代价: {total_cost}\n"
            log += f"总行动步数: {len(path)-1} 步\n"  
            log += f"路径: {' -> '.join(map(str, path))}"
            self.result_text.set(log)
            self.draw_path(path)
        else:
            self.result_text.set("无解：被假KFS彻底封死了所有可能路线。")

    def draw_path(self, path):
        coords = [(20 + (n-1)%3*120 + 60, 20 + (n-1)//3*120 + 60) for n in path]
        for i in range(len(coords) - 1):
            x1, y1 = coords[i]; x2, y2 = coords[i+1]
            offset = (i % 3 - 1) * 6
            line_id = self.canvas.create_line(x1+offset, y1+offset, x2+offset, y2+offset, arrow=tk.LAST, width=4, fill="#2b580c", smooth=True)
            mid_x, mid_y = (x1+x2)/2, (y1+y2)/2
            bg_id = self.canvas.create_oval(mid_x-9, mid_y-9, mid_x+9, mid_y+9, fill="#2b580c", outline="")
            text_id = self.canvas.create_text(mid_x, mid_y, text=str(i+1), fill="white", font=("Arial", 10, "bold"))
            self.path_elements.extend([line_id, bg_id, text_id])

if __name__ == "__main__":
    root = tk.Tk()
    app = MerlinWeightedPathFinder(root)
    root.mainloop()