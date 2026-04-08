import tkinter as tk
from tkinter import filedialog, messagebox
import random
import os

# CHIP-8 Standard Fontset
FONTSET = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
    0x20, 0x60, 0x20, 0x20, 0x70,  # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
    0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
    0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
    0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
    0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
    0xF0, 0x80, 0xF0, 0x80, 0x80   # F
]

# Map QWERTY keys to CHIP-8 Hex Keyboard
# CHIP-8:       QWERTY:
# 1 2 3 C       1 2 3 4
# 4 5 6 D  -->  Q W E R
# 7 8 9 E       A S D F
# A 0 B F       Z X C V
KEY_MAP = {
    '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
    'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
    'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
    'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF
}

class Chip8Core:
    """The Core Engine handling CHIP-8 CPU logic, Memory, and Registers."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.memory = bytearray(4096)
        self.v = bytearray(16)        # Registers V0 to VF
        self.i = 0                    # Index register
        self.pc = 0x200               # Program counter starts at 0x200
        self.stack = []               # Stack for subroutines
        self.sp = 0                   # Stack pointer
        
        self.delay_timer = 0
        self.sound_timer = 0
        
        self.gfx = bytearray(64 * 32) # 64x32 monochrome display
        self.draw_flag = True         # Signals the GUI to update
        
        self.key = bytearray(16)      # Keypad state
        self.wait_key_reg = -1        # Register waiting for key press (-1 means not waiting)
        
        # Load fontset into memory (0x050 - 0x09F)
        for i, byte in enumerate(FONTSET):
            self.memory[0x050 + i] = byte

    def load_rom(self, rom_data):
        self.reset()
        for i, byte in enumerate(rom_data):
            if 0x200 + i < 4096:
                self.memory[0x200 + i] = byte

    def cycle(self):
        # If waiting for a key press (Fx0A opcode)
        if self.wait_key_reg != -1:
            for i in range(16):
                if self.key[i]:
                    self.v[self.wait_key_reg] = i
                    self.wait_key_reg = -1
                    return
            return # Halt execution until key is pressed

        # Fetch Opcode (2 bytes)
        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.pc += 2

        # Decode & Execute
        nibble = (opcode & 0xF000) >> 12
        x = (opcode & 0x0F00) >> 8
        y = (opcode & 0x00F0) >> 4
        n = opcode & 0x000F
        nn = opcode & 0x00FF
        nnn = opcode & 0x0FFF

        if opcode == 0x00E0: # CLS
            self.gfx = bytearray(64 * 32)
            self.draw_flag = True
        elif opcode == 0x00EE: # RET
            if self.stack:
                self.pc = self.stack.pop()
        elif nibble == 0x1: # JP addr
            self.pc = nnn
        elif nibble == 0x2: # CALL addr
            self.stack.append(self.pc)
            self.pc = nnn
        elif nibble == 0x3: # SE Vx, byte
            if self.v[x] == nn: self.pc += 2
        elif nibble == 0x4: # SNE Vx, byte
            if self.v[x] != nn: self.pc += 2
        elif nibble == 0x5: # SE Vx, Vy
            if self.v[x] == self.v[y]: self.pc += 2
        elif nibble == 0x6: # LD Vx, byte
            self.v[x] = nn
        elif nibble == 0x7: # ADD Vx, byte
            self.v[x] = (self.v[x] + nn) & 0xFF
        elif nibble == 0x8:
            if n == 0x0: # LD Vx, Vy
                self.v[x] = self.v[y]
            elif n == 0x1: # OR Vx, Vy
                self.v[x] |= self.v[y]
            elif n == 0x2: # AND Vx, Vy
                self.v[x] &= self.v[y]
            elif n == 0x3: # XOR Vx, Vy
                self.v[x] ^= self.v[y]
            elif n == 0x4: # ADD Vx, Vy
                total = self.v[x] + self.v[y]
                self.v[0xF] = 1 if total > 255 else 0
                self.v[x] = total & 0xFF
            elif n == 0x5: # SUB Vx, Vy
                self.v[0xF] = 1 if self.v[x] >= self.v[y] else 0
                self.v[x] = (self.v[x] - self.v[y]) & 0xFF
            elif n == 0x6: # SHR Vx {, Vy}
                self.v[0xF] = self.v[x] & 0x1
                self.v[x] = (self.v[x] >> 1) & 0xFF
            elif n == 0x7: # SUBN Vx, Vy
                self.v[0xF] = 1 if self.v[y] >= self.v[x] else 0
                self.v[x] = (self.v[y] - self.v[x]) & 0xFF
            elif n == 0xE: # SHL Vx {, Vy}
                self.v[0xF] = (self.v[x] & 0x80) >> 7
                self.v[x] = (self.v[x] << 1) & 0xFF
        elif nibble == 0x9: # SNE Vx, Vy
            if self.v[x] != self.v[y]: self.pc += 2
        elif nibble == 0xA: # LD I, addr
            self.i = nnn
        elif nibble == 0xB: # JP V0, addr
            self.pc = nnn + self.v[0]
        elif nibble == 0xC: # RND Vx, byte
            self.v[x] = random.randint(0, 255) & nn
        elif nibble == 0xD: # DRW Vx, Vy, nibble
            vx = self.v[x] & 63
            vy = self.v[y] & 31
            self.v[0xF] = 0
            for row in range(n):
                y_coord = vy + row
                if y_coord >= 32: break # Clip at screen bottom edge
                sprite_byte = self.memory[self.i + row]
                
                for col in range(8):
                    x_coord = vx + col
                    if x_coord >= 64: break # Clip at screen right edge
                    
                    sprite_pixel = sprite_byte & (0x80 >> col)
                    if sprite_pixel:
                        idx = x_coord + (y_coord * 64)
                        if self.gfx[idx] == 1:
                            self.v[0xF] = 1 # Collision detected
                        self.gfx[idx] ^= 1
            self.draw_flag = True
        elif nibble == 0xE:
            if nn == 0x9E: # SKP Vx
                if self.key[self.v[x]]: self.pc += 2
            elif nn == 0xA1: # SKNP Vx
                if not self.key[self.v[x]]: self.pc += 2
        elif nibble == 0xF:
            if nn == 0x07: # LD Vx, DT
                self.v[x] = self.delay_timer
            elif nn == 0x0A: # LD Vx, K
                self.wait_key_reg = x
            elif nn == 0x15: # LD DT, Vx
                self.delay_timer = self.v[x]
            elif nn == 0x18: # LD ST, Vx
                self.sound_timer = self.v[x]
            elif nn == 0x1E: # ADD I, Vx
                self.i = (self.i + self.v[x]) & 0xFFFF
            elif nn == 0x29: # LD F, Vx
                self.i = 0x050 + (self.v[x] * 5)
            elif nn == 0x33: # LD B, Vx
                self.memory[self.i] = self.v[x] // 100
                self.memory[self.i + 1] = (self.v[x] // 10) % 10
                self.memory[self.i + 2] = self.v[x] % 10
            elif nn == 0x55: # LD [I], Vx
                for idx in range(x + 1):
                    self.memory[self.i + idx] = self.v[idx]
            elif nn == 0x65: # LD Vx, [I]
                for idx in range(x + 1):
                    self.v[idx] = self.memory[self.i + idx]

    def update_timers(self):
        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1

class CatsEmulatorGUI:
    """The mGBA-style Tkinter GUI encapsulating the CHIP-8 engine."""
    def __init__(self, root):
        self.root = root
        self.root.title("Cat's Chip 8 Emulator v1.0")
        self.root.geometry("600x400")
        self.root.configure(bg="#1E1E1E")
        self.root.resizable(False, False)
        
        self.chip8 = Chip8Core()
        self.rom_loaded = False
        self.paused = False
        self.current_rom_path = ""
        
        self.setup_ui()
        self.setup_bindings()
        
        # CPU speed (~600Hz / 60fps = 10 instructions per frame)
        self.instructions_per_frame = 10
        self.running = True
        self.run_loop()

    def setup_ui(self):
        # Menu Bar (mGBA aesthetic)
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Load ROM...", command=self.load_rom)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.exit_app)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Emulation Menu
        emu_menu = tk.Menu(menubar, tearoff=0)
        emu_menu.add_command(label="Pause / Resume", command=self.toggle_pause)
        emu_menu.add_command(label="Reset", command=self.reset_emulation)
        menubar.add_cascade(label="Emulation", menu=emu_menu)
        
        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        # Game Canvas (Aspect ratio 2:1 -> 64x32)
        # Using 512x256 visually to fit well within 600x400 with status bars
        self.canvas_width = 512
        self.canvas_height = 256
        self.pixel_size_x = self.canvas_width // 64
        self.pixel_size_y = self.canvas_height // 32
        
        # Centering container
        self.frame = tk.Frame(self.root, bg="#1E1E1E")
        self.frame.pack(expand=True)
        
        self.canvas = tk.Canvas(self.frame, width=self.canvas_width, height=self.canvas_height, 
                                bg="black", highlightthickness=2, highlightbackground="#333333")
        self.canvas.pack(pady=20)
        
        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready. Go to File -> Load ROM to begin.")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, 
                                   anchor=tk.W, bg="#333333", fg="white", font=("Arial", 9))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Pre-calculate and draw rectangles for the canvas to optimize drawing speed
        self.pixels = []
        self.last_gfx = bytearray(64 * 32)
        
        for y in range(32):
            for x in range(64):
                x1 = x * self.pixel_size_x
                y1 = y * self.pixel_size_y
                x2 = x1 + self.pixel_size_x
                y2 = y1 + self.pixel_size_y
                # Create default black squares
                rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill="black", outline="black")
                self.pixels.append(rect)

    def setup_bindings(self):
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)

    def on_key_press(self, event):
        key = event.keysym.lower()
        if key in KEY_MAP:
            self.chip8.key[KEY_MAP[key]] = 1

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in KEY_MAP:
            self.chip8.key[KEY_MAP[key]] = 0

    def load_rom(self):
        filepath = filedialog.askopenfilename(
            title="Load CHIP-8 ROM",
            filetypes=(("CHIP-8 ROMs", "*.ch8 *.bin *.rom"), ("All Files", "*.*"))
        )
        if filepath:
            try:
                with open(filepath, 'rb') as f:
                    rom_data = f.read()
                self.current_rom_path = filepath
                self.chip8.load_rom(rom_data)
                self.rom_loaded = True
                self.paused = False
                self.status_var.set(f"Running: {os.path.basename(filepath)}")
                # Clear previous screen cache to force full redraw
                self.last_gfx = bytearray(64 * 32) 
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load ROM:\n{str(e)}")

    def toggle_pause(self):
        if not self.rom_loaded: return
        self.paused = not self.paused
        if self.paused:
            self.status_var.set(f"Paused: {os.path.basename(self.current_rom_path)}")
        else:
            self.status_var.set(f"Running: {os.path.basename(self.current_rom_path)}")

    def reset_emulation(self):
        if self.current_rom_path:
            with open(self.current_rom_path, 'rb') as f:
                rom_data = f.read()
            self.chip8.load_rom(rom_data)
            self.last_gfx = bytearray(64 * 32)
            self.paused = False
            self.status_var.set(f"Reset: {os.path.basename(self.current_rom_path)}")

    def show_about(self):
        about_text = (
            "Cat's Chip 8 Emulator v1.0\n\n"
            "A lightweight CHIP-8 emulator built with Python and Tkinter.\n"
            "Designed with an mGBA-inspired GUI.\n\n"
            "Controls (QWERTY mapped to Hex):\n"
            "1 2 3 4 -> 1 2 3 C\n"
            "Q W E R -> 4 5 6 D\n"
            "A S D F -> 7 8 9 E\n"
            "Z X C V -> A 0 B F\n"
        )
        messagebox.showinfo("About", about_text)

    def exit_app(self):
        self.running = False
        self.root.quit()

    def render_screen(self):
        """Update only the pixels that changed to maximize Tkinter Canvas performance."""
        for i in range(2048):
            current_val = self.chip8.gfx[i]
            if current_val != self.last_gfx[i]:
                color = "#99FF99" if current_val else "black" # Retro green color
                self.canvas.itemconfig(self.pixels[i], fill=color, outline=color)
                self.last_gfx[i] = current_val

    def run_loop(self):
        """Main emulator loop firing roughly at 60Hz"""
        if not self.running:
            return

        if self.rom_loaded and not self.paused:
            # Emulate CPU Cycles
            for _ in range(self.instructions_per_frame):
                self.chip8.cycle()

            # Emulate 60Hz Timers
            self.chip8.update_timers()

            # Render Screen if draw flag is set
            if self.chip8.draw_flag:
                self.render_screen()
                self.chip8.draw_flag = False

        # Schedule next frame (~16ms is roughly 60 FPS)
        self.root.after(16, self.run_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = CatsEmulatorGUI(root)
    
    # Graceful exit handling
    root.protocol("WM_DELETE_WINDOW", app.exit_app)
    
    root.mainloop()
