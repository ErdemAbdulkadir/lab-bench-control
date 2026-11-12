from .visa_device import VisaDevice


class PowerSupply(VisaDevice):
    """Rigol DP932 (3 kanal) kontrol katmanı."""

    def set_voltage(self, channel: int, volts: float):
        self.write(f":SOURce{channel}:VOLTage {volts}")

    def set_current(self, channel: int, amps: float):
        self.write(f":SOURce{channel}:CURRent {amps}")

    def set_output(self, channel: int, on: bool):
        self.write(f":OUTP CH{channel},{'ON' if on else 'OFF'}")

    def set_all_outputs(self, on: bool):
        self.write(f":OUTP ALL,{'ON' if on else 'OFF'}")

    def read_voltage(self, channel: int) -> float:
        return self._to_float(self.query(f":MEAS:VOLT? CH{channel}"))

    def read_current(self, channel: int) -> float:
        return self._to_float(self.query(f":MEAS:CURR? CH{channel}"))

    def read_power(self, channel: int) -> float:
        return self._to_float(self.query(f":MEAS:POWE? CH{channel}"))

    def read_settings(self, channel: int):
        v = self._to_float(self.query(f":SOURce{channel}:VOLTage?"))
        c = self._to_float(self.query(f":SOURce{channel}:CURRent?"))
        return v, c

    def get_output_state(self, channel: int) -> bool:
        resp = self.query(f":OUTP? CH{channel}").strip().upper()
        # DP932 '1'/'0' donduruyor; bazi modeller 'ON'/'OFF'
        return resp in ("1", "ON")

    @staticmethod
    def _to_float(s: str) -> float:
        try:
            return float(s.strip().strip("AWV"))
        except ValueError:
            return float("nan")
