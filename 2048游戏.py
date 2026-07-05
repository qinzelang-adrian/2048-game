"""2048 游戏 - 使用 pygame

功能：
- 方向键移动/合并方块
- 平滑合并/移动动画
- 撤销功能（按 Z 悔一步）
- 游戏结束 / 胜利（凑出 2048）判定
"""

import pygame
import random

pygame.init()

# ============ 常量定义 ============
GRID_SIZE = 4
CELL_SIZE = 100
CELL_MARGIN = 12
BOARD_MARGIN = 20
TOP_BAR_HEIGHT = 120

BOARD_PIXELS = GRID_SIZE * CELL_SIZE + (GRID_SIZE + 1) * CELL_MARGIN
SCREEN_WIDTH = BOARD_PIXELS + BOARD_MARGIN * 2
SCREEN_HEIGHT = BOARD_PIXELS + BOARD_MARGIN * 2 + TOP_BAR_HEIGHT

FPS = 60
ANIM_DURATION = 120  # 毫秒

# 颜色
BG_COLOR = (250, 248, 239)
BOARD_COLOR = (187, 173, 160)
EMPTY_CELL_COLOR = (205, 193, 180)
TEXT_DARK = (119, 110, 101)
TEXT_LIGHT = (249, 246, 242)

TILE_COLORS = {
    0: (205, 193, 180),
    2: (238, 228, 218),
    4: (237, 224, 200),
    8: (242, 177, 121),
    16: (245, 149, 99),
    32: (246, 124, 95),
    64: (246, 94, 59),
    128: (237, 207, 114),
    256: (237, 204, 97),
    512: (237, 200, 80),
    1024: (237, 197, 63),
    2048: (237, 194, 46),
}
TILE_COLOR_DEFAULT = (60, 58, 50)  # 超过2048的方块


def tile_color(value):
    return TILE_COLORS.get(value, TILE_COLOR_DEFAULT)


def tile_text_color(value):
    return TEXT_DARK if value <= 4 else TEXT_LIGHT


def cell_pos(row, col):
    """返回格子左上角像素坐标"""
    x = BOARD_MARGIN + CELL_MARGIN + col * (CELL_SIZE + CELL_MARGIN)
    y = BOARD_MARGIN + TOP_BAR_HEIGHT + CELL_MARGIN + row * (CELL_SIZE + CELL_MARGIN)
    return x, y


# ============ 数据结构：单个方块（用于动画） ============
class Tile:
    """一个方块的动画状态：从起点滑动/缩放到终点"""

    def __init__(self, value, row, col, from_row=None, from_col=None, spawning=False, merged=False):
        self.value = value
        self.row = row
        self.col = col
        self.from_row = from_row if from_row is not None else row
        self.from_col = from_col if from_col is not None else col
        self.spawning = spawning  # 新生成的方块，做缩放出现动画
        self.merged = merged      # 合并结果方块，做“弹一下”动画
        self.start_time = pygame.time.get_ticks()

    def progress(self):
        elapsed = pygame.time.get_ticks() - self.start_time
        return min(1.0, elapsed / ANIM_DURATION)

    def is_done(self):
        return self.progress() >= 1.0

    def current_pixel_rect(self):
        t = self._ease(self.progress())
        fx, fy = cell_pos(self.from_row, self.from_col)
        tx, ty = cell_pos(self.row, self.col)
        x = fx + (tx - fx) * t
        y = fy + (ty - fy) * t

        size = CELL_SIZE
        if self.spawning:
            scale = 0.3 + 0.7 * t
            size = CELL_SIZE * scale
            x += (CELL_SIZE - size) / 2
            y += (CELL_SIZE - size) / 2
        elif self.merged:
            # 合并完成前做一次更夸张的“弹一下”放大再恢复
            bump = 1.0 + 0.18 * self.merge_flash_intensity()
            size = CELL_SIZE * bump
            x -= (size - CELL_SIZE) / 2
            y -= (size - CELL_SIZE) / 2

        return pygame.Rect(int(x), int(y), int(size), int(size))

    def merge_flash_intensity(self):
        """合并弹跳的强度包络：0 -> 1 -> 0，中间用 smoothstep 让弹跳更有力度"""
        if not self.merged:
            return 0.0
        t = self.progress()
        envelope = max(0.0, 1 - abs(2 * t - 1))
        return envelope * envelope * (3 - 2 * envelope)

    @staticmethod
    def _ease(t):
        # ease-out
        return 1 - (1 - t) ** 3


# ============ 游戏核心逻辑 ============
class Board:
    # 每个方向的坐标映射规则：(is_row, reverse)
    # is_row=True 表示沿着"行"压缩（一行内按列移动），False 表示沿着"列"压缩
    # reverse=True 表示"抽取行"时按坐标从大到小扫描（right/down 最终堆到大坐标一端，
    # 但因压缩算法统一按"堆向数组前端"实现，所以要反过来从大坐标往小坐标扫描取值）
    _DIRECTION_CONFIG = {
        "left": (True, False),
        "right": (True, True),
        "up": (False, False),
        "down": (False, True),
    }

    def __init__(self):
        self.grid = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        self.score = 0

    def clone_state(self):
        return [row[:] for row in self.grid], self.score

    def restore_state(self, state):
        grid, score = state
        self.grid = [row[:] for row in grid]
        self.score = score

    def add_random_tile(self):
        empties = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE) if self.grid[r][c] == 0]
        if not empties:
            return None
        r, c = random.choice(empties)
        value = 4 if random.random() < 0.1 else 2
        self.grid[r][c] = value
        return r, c, value

    def has_moves(self):
        """是否还有可移动/合并的空间"""
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if self.grid[r][c] == 0:
                    return True
                if c + 1 < GRID_SIZE and self.grid[r][c] == self.grid[r][c + 1]:
                    return True
                if r + 1 < GRID_SIZE and self.grid[r][c] == self.grid[r + 1][c]:
                    return True
        return False

    def has_won(self):
        return any(self.grid[r][c] >= 2048 for r in range(GRID_SIZE) for c in range(GRID_SIZE))

    def move(self, direction):
        """
        执行一次移动。direction: 'up'/'down'/'left'/'right'
        返回 (moved: bool, tiles_animation: list[Tile], gained_score: int)
        """
        moved = False
        gained_score = 0
        animations = []

        # 统一转换成“向左压缩”的行来处理，再映射回原方向
        lines = self._extract_lines(direction)

        new_lines = []
        for line_index, line in enumerate(lines):
            # line: list of (value, original_row, original_col)
            merged_line, line_moved, line_score, line_anims = self._merge_line(line, direction, line_index)
            new_lines.append(merged_line)
            moved = moved or line_moved
            gained_score += line_score
            animations.extend(line_anims)

        if moved:
            self._write_lines_back(direction, new_lines)
            self.score += gained_score

        return moved, animations, gained_score

    def _extract_lines(self, direction):
        """把网格按移动方向抽取成一组“行”，每行是要挤压的一维序列"""
        is_row, reverse = self._DIRECTION_CONFIG[direction]
        indices = range(GRID_SIZE - 1, -1, -1) if reverse else range(GRID_SIZE)

        lines = []
        if is_row:
            for r in range(GRID_SIZE):
                lines.append([(self.grid[r][c], r, c) for c in indices])
        else:
            for c in range(GRID_SIZE):
                lines.append([(self.grid[r][c], r, c) for r in indices])
        return lines

    def _merge_line(self, line, direction, line_index):
        """
        对一行做"向左压缩+合并"，line 中的顺序已经是目标方向的压缩顺序。
        返回：new_line(与line同长度，(value, tgt_row, tgt_col)，即压缩后的目标坐标)，是否移动，得分，动画列表
        """
        values = [v for v, _, _ in line if v != 0]
        positions = [(r, c) for v, r, c in line if v != 0]

        merged_values = []
        merged_from = []  # 每个结果格子对应的原始位置列表（1个或2个，用于动画来源）
        score = 0

        i = 0
        while i < len(values):
            if i + 1 < len(values) and values[i] == values[i + 1]:
                merged_values.append(values[i] * 2)
                merged_from.append([positions[i], positions[i + 1]])
                score += values[i] * 2
                i += 2
            else:
                merged_values.append(values[i])
                merged_from.append([positions[i]])
                i += 1

        # 补齐0
        while len(merged_values) < GRID_SIZE:
            merged_values.append(0)
            merged_from.append([])

        # 计算目标位置（按方向映射回真实行列），并生成动画和 new_line
        target_positions = self._line_target_positions(direction, line_index)

        new_line = []
        animations = []
        moved = False

        for idx, value in enumerate(merged_values):
            tgt_r, tgt_c = target_positions[idx]
            new_line.append((value, tgt_r, tgt_c))
            froms = merged_from[idx]
            if value == 0:
                continue
            if len(froms) == 2:
                (r1, c1), (r2, c2) = froms
                animations.append(Tile(value, tgt_r, tgt_c, from_row=r1, from_col=c1))
                animations.append(Tile(value, tgt_r, tgt_c, from_row=r2, from_col=c2, merged=True))
                moved = True  # 两格合并本身即视为发生了变化
            else:
                (r1, c1) = froms[0]
                animations.append(Tile(value, tgt_r, tgt_c, from_row=r1, from_col=c1))
                if (r1, c1) != (tgt_r, tgt_c):
                    moved = True

        return new_line, moved, score, animations

    def _line_target_positions(self, direction, line_index):
        """给定方向和行/列序号，返回该行压缩后各槽位对应的真实(row, col)，按目标顺序"""
        is_row, reverse = self._DIRECTION_CONFIG[direction]
        coords = [GRID_SIZE - 1 - c if reverse else c for c in range(GRID_SIZE)]
        if is_row:
            return [(line_index, c) for c in coords]
        return [(c, line_index) for c in coords]

    def _write_lines_back(self, direction, new_lines):
        for line in new_lines:
            for value, r, c in line:
                self.grid[r][c] = value


# ============ 游戏主类 ============
class Game:
    KEY_DIRECTION = {
        pygame.K_UP: "up",
        pygame.K_DOWN: "down",
        pygame.K_LEFT: "left",
        pygame.K_RIGHT: "right",
    }

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("2048")
        self.clock = pygame.time.Clock()
        self.font_score = pygame.font.SysFont("simhei,microsoftyahei,arial", 28, bold=True)
        self.font_score_label = pygame.font.SysFont("simhei,microsoftyahei,arial", 18, bold=True)
        self.font_title = pygame.font.SysFont("simhei,microsoftyahei,arial", 40, bold=True)
        self.font_tile_big = pygame.font.SysFont("arial", 44, bold=True)
        self.font_tile_small = pygame.font.SysFont("arial", 32, bold=True)
        self.font_msg = pygame.font.SysFont("simhei,microsoftyahei,arial", 34, bold=True)
        self.font_hint = pygame.font.SysFont("simhei,microsoftyahei,arial", 20)

        # 静态文字只需渲染一次，缓存起来，避免每帧重复 render
        self.title_surf = self.font_title.render("2048", True, TEXT_DARK)
        hint_text = "方向键 移动  |  Z 悔一步  |  R 重新开始"
        self.hint_surf = self.font_hint.render(hint_text, True, TEXT_DARK)
        self.score_label_surf = self.font_score_label.render("得分", True, (238, 228, 218))

        # 方块数字取值范围很小，渲染一次按数值缓存，避免每帧重复 render
        self._tile_text_cache = {}
        # 分数只在变化时才需要重新渲染
        self._score_value = None
        self._score_value_surf = None

        self.board_background = self._build_board_background()

        self.history = []  # 撤销栈：存 (grid_state, score)，game_won/game_over 在 undo 时重新计算
        self.animations = []
        self.animating = False
        self.anim_phase = None  # "move" -> 移动/合并动画阶段, "spawn" -> 新方块生成动画阶段

        self.new_game()

    def new_game(self):
        self.board = Board()
        self.history.clear()
        self.game_over = False
        self.game_won = False  # 是否已凑出 2048，凑出即直接结束游戏
        self.animations.clear()
        self.animating = False
        self.anim_phase = None
        self.board.add_random_tile()
        self.board.add_random_tile()

    # ---------- 输入处理 ----------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key in self.KEY_DIRECTION and not self.animating and not self.game_over and not self.game_won:
                    self.try_move(self.KEY_DIRECTION[event.key])
                elif event.key == pygame.K_z:
                    self.undo()
                elif event.key == pygame.K_r:
                    self.new_game()
                elif event.key == pygame.K_SPACE and (self.game_over or self.game_won):
                    self.new_game()
        return True

    def try_move(self, direction):
        # 保存历史用于撤销
        snapshot = self.board.clone_state()

        moved, animations, _ = self.board.move(direction)
        if not moved:
            return

        self.history.append(snapshot)
        if len(self.history) > 50:
            self.history.pop(0)

        self.animations = animations
        self.animating = True
        self.anim_phase = "move"

    def finish_move(self):
        """移动/合并动画结束后：生成新方块（带生成动画）+ 判定输赢"""
        spawn = self.board.add_random_tile()

        if spawn:
            spawn_row, spawn_col, _ = spawn
            static_tiles = []
            for r in range(GRID_SIZE):
                for c in range(GRID_SIZE):
                    value = self.board.grid[r][c]
                    if value == 0:
                        continue
                    spawning = (r, c) == (spawn_row, spawn_col)
                    static_tiles.append(Tile(value, r, c, spawning=spawning))
            self.animations = static_tiles
            self.anim_phase = "spawn"
            self.animating = True
        else:
            self.animations = []
            self.anim_phase = None
            self.animating = False

        if self.board.has_won() and not self.game_won:
            self.game_won = True
        if not self.board.has_moves() and not self.game_over:
            self.game_over = True

    def undo(self):
        if self.history and not self.animating:
            state = self.history.pop()
            self.board.restore_state(state)
            self.game_over = False
            self.game_won = self.board.has_won()
            self.animations.clear()
            self.animating = False
            self.anim_phase = None

    # ---------- 更新 ----------
    def update(self):
        if self.animating and all(a.is_done() for a in self.animations):
            if self.anim_phase == "move":
                self.finish_move()
            elif self.anim_phase == "spawn":
                self.animating = False
                self.anim_phase = None

    # ---------- 绘制 ----------
    def draw(self):
        self.screen.fill(BG_COLOR)
        self._draw_top_bar()
        self._draw_board_background()

        if self.animating:
            # 每个 tile 的 rect/flash 每帧只算一次，供光晕和方块本体两次绘制共用
            frame_tiles = [(t, t.current_pixel_rect(), t.merge_flash_intensity()) for t in self.animations]
            for tile, rect, flash in frame_tiles:
                if tile.merged:
                    self._draw_merge_glow(rect, flash)
            for tile, rect, flash in frame_tiles:
                self._draw_tile_rect(tile.value, rect, flash=flash)
        else:
            for r in range(GRID_SIZE):
                for c in range(GRID_SIZE):
                    value = self.board.grid[r][c]
                    if value:
                        x, y = cell_pos(r, c)
                        rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
                        self._draw_tile_rect(value, rect)

        if self.game_won:
            self._draw_overlay("恭喜达成 2048！你赢了 —— 按 R 重新开始 / Z 悔一步")
        elif self.game_over:
            self._draw_overlay("游戏结束！按 R 重新开始 / Z 悔一步")

        pygame.display.flip()

    def _draw_top_bar(self):
        self.screen.blit(self.title_surf, (BOARD_MARGIN, 15))
        self._draw_score_box(self.board.score, SCREEN_WIDTH - 120 - BOARD_MARGIN, 15)
        self.screen.blit(self.hint_surf, (BOARD_MARGIN, 90))

    def _draw_score_box(self, value, x, y):
        box_w, box_h = 120, 65
        rect = pygame.Rect(x, y, box_w, box_h)
        pygame.draw.rect(self.screen, BOARD_COLOR, rect, border_radius=8)

        if value != self._score_value:
            self._score_value = value
            self._score_value_surf = self.font_score.render(str(value), True, TEXT_LIGHT)

        self.screen.blit(self.score_label_surf, (rect.centerx - self.score_label_surf.get_width() // 2, rect.y + 8))
        value_surf = self._score_value_surf
        self.screen.blit(value_surf, (rect.centerx - value_surf.get_width() // 2, rect.y + 28))

    def _build_board_background(self):
        """棋盘底板+空格子从不随游戏变化，预渲染成一张 Surface，之后每帧直接 blit"""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        board_rect = pygame.Rect(
            BOARD_MARGIN, BOARD_MARGIN + TOP_BAR_HEIGHT,
            BOARD_PIXELS, BOARD_PIXELS
        )
        pygame.draw.rect(surf, BOARD_COLOR, board_rect, border_radius=8)
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                x, y = cell_pos(r, c)
                rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(surf, EMPTY_CELL_COLOR, rect, border_radius=6)
        return surf.convert_alpha()

    def _draw_board_background(self):
        self.screen.blit(self.board_background, (0, 0))

    def _draw_merge_glow(self, rect, intensity):
        """合并瞬间在方块背后画一圈扩散淡出的光晕，增强“炫酷”视觉冲击"""
        if intensity <= 0:
            return
        # 叠几层逐渐变大、变淡的矩形，模拟柔和的模糊光晕
        layers = 4
        max_size = int(rect.width * (1.0 + 0.5 * intensity))
        for i in range(layers, 0, -1):
            layer_t = i / layers
            layer_size = int(rect.width + (max_size - rect.width) * layer_t)
            glow_surf = pygame.Surface((layer_size, layer_size), pygame.SRCALPHA)
            alpha = int(45 * intensity * (1 - layer_t) + 10)
            pygame.draw.rect(
                glow_surf, (255, 245, 210, alpha),
                glow_surf.get_rect(), border_radius=layer_size // 3
            )
            glow_rect = glow_surf.get_rect(center=rect.center)
            self.screen.blit(glow_surf, glow_rect)

    def _draw_tile_rect(self, value, rect, flash=0.0):
        color = tile_color(value)
        if flash > 0:
            color = tuple(int(c + (255 - c) * flash * 0.6) for c in color)
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        text_surf = self._get_tile_text_surface(value)
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)

    def _get_tile_text_surface(self, value):
        text_surf = self._tile_text_cache.get(value)
        if text_surf is None:
            font = self.font_tile_big if value < 1000 else self.font_tile_small
            text_surf = font.render(str(value), True, tile_text_color(value))
            self._tile_text_cache[value] = text_surf
        return text_surf

    def _draw_overlay(self, message):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, 160))
        self.screen.blit(overlay, (0, 0))

        msg_surf = self.font_msg.render(message, True, TEXT_DARK)
        msg_rect = msg_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(msg_surf, msg_rect)

    # ---------- 主循环 ----------
    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


if __name__ == "__main__":
    Game().run()