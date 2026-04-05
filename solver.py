import heapq
import itertools
from dataclasses import dataclass

class SolverConfigError(ValueError):
    """布局或配置不合法时抛出。"""
@dataclass
class SolveResult:
    path: list
    total_cost: float

class MerlinALLRouter:
    """算法调用类：封装校验、最短路与全局寻优。"""
    def __init__(self, entry_nodes=(1, 2, 3), exit_nodes=(10, 11, 12)):
        self.entry_nodes = entry_nodes
        self.exit_nodes = exit_nodes

    def _solve_weighted_route(self, piles):
        if set(piles.keys()) != set(range(1, 13)):
            raise SolverConfigError("piles 必须包含 id 1..12 的全部桩")

        r2_nodes = [pid for pid, pile in piles.items() if pile.block_type == "R2"]
        r1_nodes = [pid for pid, pile in piles.items() if pile.block_type == "R1"]
        fake_nodes = [pid for pid, pile in piles.items() if pile.block_type == "FAKE"]
        # required_r2 = self.required_counts.get("R2", 0)
        # required_r1 = self.required_counts.get("R1", 0)
        # required_fake = self.required_counts.get("FAKE", 0)

        # if len(r2_nodes) != required_r2 or len(r1_nodes) != required_r1 or len(fake_nodes) != required_fake:
        #     raise SolverConfigError(
        #         f"必须放置 {required_r2}个R2, {required_r1}个R1, {required_fake}个假KFS"
        #     )
        # if any(node in self.entry_nodes for node in fake_nodes):
        #     entries = ", ".join(str(n) for n in self.entry_nodes)
        #     raise SolverConfigError(f"{entries} 号桩不可放假KFS")
        r2_in_entry = [n for n in r2_nodes if n in self.entry_nodes]
        if r2_in_entry:
            starts = r2_in_entry
        else:
            starts = [n for n in self.entry_nodes if n not in fake_nodes]

        exits = [n for n in self.exit_nodes if n not in fake_nodes]
        best_path = None
        min_total_cost = float("inf")

        for start in starts:
            for r2_seq in itertools.permutations(r2_nodes):
                for ex in exits:
                    current_cost = 0
                    current_full_path = []
                    valid_route = True
                    checkpoints = [start] + list(r2_seq) + [ex]

                    for i in range(len(checkpoints) - 1):
                        p1, p2 = checkpoints[i], checkpoints[i + 1]
                        if p1 == p2:
                            continue

                        if piles[p1].block_type == "FAKE" or piles[p2].block_type == "FAKE":
                            valid_route = False
                            break

                        queue = [(0, p1, [p1])]
                        min_cost_to_node = {p1: 0}
                        sub_path = None
                        sub_cost = float("inf")

                        while queue:
                            cost, curr, path = heapq.heappop(queue)

                            if cost > min_cost_to_node.get(curr, float("inf")):
                                continue

                            if curr == p2:
                                sub_path = path
                                sub_cost = cost
                                break

                            row, col = (curr - 1) // 3, (curr - 1) % 3
                            neighbors = []
                            if row > 0:
                                neighbors.append(curr - 3)
                            if row < 3:
                                neighbors.append(curr + 3)
                            if col > 0:
                                neighbors.append(curr - 1)
                            if col < 2:
                                neighbors.append(curr + 1)

                            for nxt in neighbors:
                                if piles[nxt].block_type == "FAKE":
                                    continue

                                step_cost = piles[nxt].cost
                                new_cost = cost + step_cost

                                if new_cost < min_cost_to_node.get(nxt, float("inf")):
                                    min_cost_to_node[nxt] = new_cost
                                    heapq.heappush(queue, (new_cost, nxt, path + [nxt]))

                        if sub_path is None:
                            valid_route = False
                            break

                        if current_full_path:
                            current_full_path.extend(sub_path[1:])
                        else:
                            current_full_path.extend(sub_path)

                        current_cost += sub_cost

                    if valid_route and current_cost < min_total_cost:
                        min_total_cost = current_cost
                        best_path = current_full_path

        return best_path, min_total_cost
    
class MerlinMasterRouter:
    """争KongFu Master的寻路逻辑，拿完一个R2 KFS就试图直接撤离，此时视R2 KFS为高代价区域，R1 KFS反而代价更低（需要R1速捡去R1 KFS配合）"""
    def __init__(self, entry_nodes=(1, 2, 3), exit_nodes=(10, 11, 12)):
        self.entry_nodes = entry_nodes
        self.exit_nodes = exit_nodes

        self.COST_EMPTY = 1    
        self.COST_R1 = 2      
        self.COST_R2 = 5      

    def _solve_two_phase_route(self, piles):
        if set(piles.keys()) != set(range(1, 13)):
            raise SolverConfigError("piles 必须包含 id 1..12 的全部桩")

        r2_nodes = [pid for pid, pile in piles.items() if pile.block_type == "R2"]
        fake_nodes = [pid for pid, pile in piles.items() if pile.block_type == "FAKE"]

        # 规则校验
        if any(node in self.entry_nodes for node in fake_nodes):
            entries = ", ".join(str(n) for n in self.entry_nodes)
            raise SolverConfigError(f"{entries} 号桩不可放假KFS")

        # 确定合法起点 (强制 R2 优先)
        r2_in_entry = [n for n in r2_nodes if n in self.entry_nodes]
        if r2_in_entry:
            starts = r2_in_entry
        else:
            starts = [n for n in self.entry_nodes if n not in fake_nodes]

        # 确定合法终点
        exits = [n for n in self.exit_nodes if n not in fake_nodes]

        best_path = None
        min_total_cost = float("inf")

        # --- 算法核心：遍历起点 -> 遍历目标 R2 -> 遍历终点 ---
        for start in starts:
            for target_r2 in r2_nodes:
                # [Phase 1] 寻宝：从起点前往选定的 R2
                path1, cost1 = self._dijkstra(start, target_r2, piles, phase=1)
                if path1 is None:
                    continue  # 走不到这个 R2，换下一个
                
                # [Phase 2] 撤离：从刚拿到的 R2 前往任意终点
                for ex in exits:
                    path2, cost2 = self._dijkstra(target_r2, ex, piles, phase=2)
                    if path2 is None:
                        continue # 从这个 R2 出不去，换下一个终点
                    
                    total_cost = cost1 + cost2
                    if total_cost < min_total_cost:
                        min_total_cost = total_cost
                        # 拼接路径 (剔除重复连接点 target_r2)
                        best_path = path1 + path2[1:]

        return best_path, min_total_cost

    def _dijkstra(self, start, end, piles, phase):
        """带地形状态感知的 Dijkstra 算法"""
        if piles[start].block_type == "FAKE" or piles[end].block_type == "FAKE":
            return None, float("inf")

        queue = [(0, start, [start])]
        min_cost_to_node = {start: 0}

        while queue:
            cost, curr, path = heapq.heappop(queue)

            if cost > min_cost_to_node.get(curr, float("inf")):
                continue

            if curr == end:
                return path, cost

            # 生成十字方向邻居
            row, col = (curr - 1) // 3, (curr - 1) % 3
            neighbors = []
            if row > 0: neighbors.append(curr - 3)
            if row < 3: neighbors.append(curr + 3)
            if col > 0: neighbors.append(curr - 1)
            if col < 2: neighbors.append(curr + 1)

            for nxt in neighbors:
                b_type = piles[nxt].block_type

                if b_type == "FAKE":
                    continue
                # 代价切换逻辑 
                if phase == 1:
                    # 寻找目标 R2
                    # R1 维持常规的高代价，空地和其他 R2 视为常规路面
                    step_cost = piles[nxt].cost if b_type == "R1" else 1
                else:
                    # Phase 2：已拿到 R2
                    if b_type == "EMPTY" or (b_type == "R2" and nxt == end): 
                        # 如果终点恰好是被挤占的，或者空地，代价最低
                        step_cost = self.COST_EMPTY
                    elif b_type == "R1":
                        step_cost = self.COST_R1
                    elif b_type == "R2":
                        # 撤离时路过其他 R2 代价比 R1 还高
                        step_cost = self.COST_R2
                    else:
                        step_cost = 1

                new_cost = cost + step_cost

                if new_cost < min_cost_to_node.get(nxt, float("inf")):
                    min_cost_to_node[nxt] = new_cost
                    heapq.heappush(queue, (new_cost, nxt, path + [nxt]))

        return None, float("inf")
    