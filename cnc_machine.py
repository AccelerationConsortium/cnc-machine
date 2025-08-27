
import logging
import serial
import time
import yaml

class CNC_Machine:
    """
    GRBL CNC controller helper with:
      - Persistent serial connection
      - Virtual (no-COM) mode for testing
      - Structured logging (DEBUG/INFO/WARNING/ERROR)
    """

    def __init__(self, com, baud_rate=115200, x_low_bound=0, x_high_bound=270, 
                 y_low_bound=0, y_high_bound=150, z_low_bound=-35, z_high_bound=0,
                 virtual=False, locations_file=None, log_level=logging.INFO,):
        self.logger = logging.getLogger(__name__ + ".CNC_Machine")
        if not self.logger.handlers:
            h = logging.StreamHandler()
            fmt = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
            h.setFormatter(fmt)
            self.logger.addHandler(h)
        self.logger.setLevel(log_level)

        # Set constants from parameters
        self.BAUD_RATE = baud_rate
        self.X_LOW_BOUND = x_low_bound
        self.X_HIGH_BOUND = x_high_bound
        self.Y_LOW_BOUND = y_low_bound
        self.Y_HIGH_BOUND = y_high_bound
        self.Z_LOW_BOUND = z_low_bound
        self.Z_HIGH_BOUND = z_high_bound

        self.VIRTUAL = virtual
        self.SERIAL_PORT = com
        self.ser = None
        self.LOCATIONS = self.load_from_yaml(locations_file)

        self._virtual_log = []
        self._virtual_state = "Idle"
        self._virtual_pos = {"X": 0.0, "Y": 0.0, "Z": 0.0}

        self.logger.info(
            "CNC_Machine initialized (virtual=%s, port=%s, baud=%s)",
            self.VIRTUAL, self.SERIAL_PORT, self.BAUD_RATE
        )

    def load_from_yaml(self, file_in):
        if not file_in:
            self.logger.warning("No locations_file provided; LOCATIONS will be empty.")
            return {}
        try:
            with open(file_in, "r") as f:
                data = yaml.safe_load(f) or {}
            self.logger.info("Loaded locations from %s", file_in)
            return data
        except FileNotFoundError:
            self.logger.error("locations_file %s not found; LOCATIONS empty.", file_in)
            return {}
        except Exception as e:
            self.logger.exception("Failed to load YAML '%s': %s", file_in, e)
            return {}

    def connect(self):
        if self.VIRTUAL:
            self.logger.info("[VIRTUAL] connect() noop.")
            return
        if self.ser and self.ser.is_open:
            self.logger.debug("Serial already open on %s", self.SERIAL_PORT)
            return
        self.logger.info("Opening serial port %s @ %s baud", self.SERIAL_PORT, self.BAUD_RATE)
        self.ser = serial.Serial(self.SERIAL_PORT, self.BAUD_RATE)
        self.wake_up()

    def close(self):
        if self.VIRTUAL:
            self.logger.info("[VIRTUAL] close() noop.")
            return
        if self.ser:
            try:
                self.logger.info("Closing serial port.")
                self.ser.close()
            finally:
                self.ser = None

    def _ensure_connected(self):
        if self.VIRTUAL:
            return
        if not self.ser or not self.ser.is_open:
            self.connect()

    def wake_up(self):
        if self.VIRTUAL:
            self.logger.debug("[VIRTUAL] wake_up() noop.")
            return
        self._ensure_connected()
        self.logger.debug("Waking GRBL and clearing greeting.")
        self.ser.reset_input_buffer()
        self.ser.write(b"\r\n\r\n")
        time.sleep(2.0)
        self.ser.reset_input_buffer()

    def _readline(self, timeout=2.0):
        if self.VIRTUAL:
            return ""
        self._ensure_connected()
        self.ser.timeout = timeout
        line = self.ser.readline()
        s = line.decode("utf-8", errors="ignore").strip()
        if s:
            self.logger.debug("<< %s", s)
        return s

    def _query_status(self):
        if self.VIRTUAL:
            s = f"<{self._virtual_state}|MPos:{self._virtual_pos['X']:.3f},{self._virtual_pos['Y']:.3f},{self._virtual_pos['Z']:.3f}|FS:0,0>"
            self.logger.debug("[VIRTUAL] ? => %s", s)
            return s
        self._ensure_connected()
        self.ser.write(b"?")
        self.logger.debug(">> ?")
        return self._readline(timeout=0.5)

    def wait_until_idle(self, poll_hz=10.0, max_s=60.0):
        if self.VIRTUAL:
            self.logger.debug("[VIRTUAL] wait_until_idle() immediate Idle.")
            return
        period = 1.0 / float(poll_hz)
        t0 = time.time()
        last = ""
        while True:
            status = self._query_status()
            last = status or last
            if status.startswith("<Idle"):
                return
            if (time.time() - t0) > max_s:
                raise TimeoutError(f"Machine did not become Idle in {max_s}s, last status: {last}")
            time.sleep(period)

    def send_lines(self, lines):
        replies = []
        if self.VIRTUAL:
            for raw in lines:
                line = (raw or "").strip()
                if not line:
                    continue
                self._virtual_log.append(line)
                self.logger.debug("[VIRTUAL] >> %s", line)
                if line.startswith(("G0", "G1", "G2", "G3")):
                    self._virtual_state = "Run"
                    for axis in ("X", "Y", "Z"):
                        if axis in line:
                            for tok in line.split():
                                if tok.startswith(axis):
                                    try:
                                        self._virtual_pos[axis] = float(tok[len(axis):])
                                    except Exception:
                                        pass
            self._virtual_state = "Idle"
            replies = ["ok" for _ in lines if (raw or "").strip()]
            self.logger.info("[VIRTUAL] Sent %d lines.", len(replies))
            return replies

        self._ensure_connected()
        for raw in lines:
            line = (raw or "").strip()
            if not line:
                continue
            self.logger.debug(">> %s", line)
            self.ser.write((line + "\n").encode("ascii"))
            while True:
                r = self._readline(timeout=2.0)
                if not r:
                    continue
                if r.startswith("ok"):
                    replies.append(r)
                    break
                if r.startswith("error:") or r.startswith("ALARM:"):
                    self.logger.error("%s (for: %s)", r, line)
                    raise RuntimeError(f"{r} (for: {line})")
        self.logger.info("Sent %d lines.", len(replies))
        return replies

    def follow_gcode_path(self, gcode_blob, wait=True):
        lines = [ln for ln in gcode_blob.splitlines() if ln.strip()]
        if not lines:
            self.logger.warning("Empty G-code blob received.")
            return []
        self.logger.debug("Dispatching %d lines.", len(lines))
        acks = self.send_lines(lines)
        if wait:
            self.wait_until_idle()
        return acks

    def set_safe_modes(self):
        self.logger.info("Setting safe modes (G21, G90, G94, G54).")
        self.follow_gcode_path("G21\nG90\nG94\nG54\n")

    def origin(self):
        self.logger.info("Returning to work origin (0,0,0).")
        self.move_to_point_safe(x=0, y=0, z=0, gtype="G0")

    def home(self, unlock=True, set_wcs_zero=True, park=(0,0,0), rapid=True):
        g = []
        if unlock:
            g.append("$X")
        g.append("$H")
        g += ["G21", "G90", "G94", "G54"]
        if set_wcs_zero:
            g.append("G10 L20 P1 X0 Y0 Z0")
        if park is not None:
            x, y, z = park
            move = "G0" if rapid else "G1"
            g += [
                f"G53 G0 Z{self.Z_HIGH_BOUND}",
                f"{move} X{float(x):.3f} Y{float(y):.3f}",
                f"{move} Z{float(z):.3f}",
            ]
        gcode = "\n".join(g) + "\n"
        self.logger.info("Starting homing sequence.")
        self.logger.debug("Homing program:\n%s", gcode)
        self.follow_gcode_path(gcode)

    def move_through_points(self, point_list, speed=3000):
        self.logger.info("Moving through %d points at F%d.", len(point_list), speed)
        lines = ["G90"]
        for (x, y, z) in point_list:
            if self.coordinates_within_bounds(x, y, z):
                lines.append(self.get_gcode_path_to_point(x, y, z, speed, "G1").strip())
            else:
                self.logger.warning("Skipped out-of-bounds point: X%s Y%s Z%s", x, y, z)
        self.follow_gcode_path("\n".join(lines) + "\n")

    def move_to_point(self, x=None, y=None, z=None, speed=3000, gtype="G1"):
        if self.coordinates_within_bounds(x, y, z):
            gcode = self.get_gcode_path_to_point(x, y, z, speed, gtype)
            self.logger.info("Move to point: X%s Y%s Z%s @ F%d (%s).", x, y, z, speed, gtype)
            return self.follow_gcode_path(gcode)
        else:
            self.logger.warning("Out of bounds: X%s Y%s Z%s", x, y, z)
            return None

    def move_to_point_safe(self, x, y, z, speed=3000, gtype="G1"):
        if self.coordinates_within_bounds(x, y, z):
            move = "G0" if gtype == "G0" else "G1"
            g = [
                f"G53 G0 Z{self.Z_HIGH_BOUND}",
                "G90",
                f"{move} X{float(x):.3f} Y{float(y):.3f} F{int(speed)}",
                f"{move} Z{float(z):.3f}",
            ]
            self.logger.info("Safe move to: X%s Y%s Z%s @ F%d.", x, y, z, speed)
            self.follow_gcode_path("\n".join(g) + "\n")
        else:
            self.logger.warning("Out of bounds (safe move): X%s Y%s Z%s", x, y, z)

    def move_to_location(self, location_name, location_index, safe=True, speed=3000):
        self.logger.info("Moving to location '%s' index %s (safe=%s).", location_name, location_index, safe)
        x, y, z = self.get_location_position(location_name, location_index)
        if safe:
            return self.move_to_point_safe(x, y, z, speed=speed)
        else:
            return self.move_to_point(x, y, z, speed=speed)

    def get_location_position(self, location_name, location_index):
        loc = self.LOCATIONS.get(location_name)
        if not loc:
            raise KeyError(f"Unknown location '{location_name}'")
        x = loc["x_origin"]; y = loc["y_origin"]; z = loc["z_origin"]
        if location_index is not None and location_index >= 0:
            nx = int(loc["num_x"]); dx = float(loc["x_offset"])
            ny = int(loc["num_y"]); dy = float(loc["y_offset"])
            col = location_index % nx
            row = location_index // nx
            x = x + col * dx
            y = y + row * dy
        self.logger.debug("Resolved location '%s'[%s] -> X%.3f Y%.3f Z%.3f", location_name, location_index, x, y, z)
        return x, y, z

    def get_gcode_path_to_point(self, x=None, y=None, z=None, speed=3000, gtype="G1"):
        parts = [gtype]
        if x is not None: parts.append(f"X{float(x):.3f}")
        if y is not None: parts.append(f"Y{float(y):.3f}")
        if z is not None: parts.append(f"Z{float(z):.3f}")
        parts.append(f"F{int(speed)}")
        cmd = " ".join(parts) + "\n"
        self.logger.debug("Built move: %s", cmd.strip())
        return cmd

    def coordinates_within_bounds(self, x, y, z):
        def ok(val, lo, hi):
            return val is None or (lo <= val <= hi)
        inside = (
            ok(x, self.X_LOW_BOUND, self.X_HIGH_BOUND) and
            ok(y, self.Y_LOW_BOUND, self.Y_HIGH_BOUND) and
            ok(z, self.Z_LOW_BOUND, self.Z_HIGH_BOUND)
        )
        if not inside:
            self.logger.debug(
                "Bounds check failed: X%s[%s..%s] Y%s[%s..%s] Z%s[%s..%s]",
                x, self.X_LOW_BOUND, self.X_HIGH_BOUND,
                y, self.Y_LOW_BOUND, self.Y_HIGH_BOUND,
                z, self.Z_LOW_BOUND, self.Z_HIGH_BOUND,
            )
        return inside
