import threading

import pyvisa

# Acik VISA kaynaklarinin global kaydi: ayni port iki cihazla da acilmasin
# (ASRL/COM portlar exclusive; cift open GUI'yi kilitliyor)
_OPEN_PORTS = {}
_registry_lock = threading.Lock()


class VisaDevice:
    """Ortak VISA bağlantı sınıfı."""

    def __init__(self):
        self.rm = None
        self.instr = None
        self._lock = threading.Lock()
        self._resource = None
        self.last_error = ""

    @staticmethod
    def list_devices():
        """USB INSTR kaynaklarını listeler."""
        try:
            rm = pyvisa.ResourceManager()
            return [r for r in rm.list_resources() if "INSTR" in r]
        except Exception:
            return []

    def connect(self, resource_name: str) -> bool:
        self.last_error = ""
        if self._resource == resource_name and self.instr is not None:
            return True  # zaten bagli
        with _registry_lock:
            holder = _OPEN_PORTS.get(resource_name)
            if holder is not None and holder is not self:
                self.last_error = (f"Bu port baska bir cihazda acik "
                                    f"(ilk önce orada bağlantıyı kesin)")
                return False
            _OPEN_PORTS[resource_name] = self
        self.disconnect()
        self.rm = pyvisa.ResourceManager()
        try:
            self.instr = self.rm.open_resource(resource_name)
            self.instr.timeout = 5000
            self._resource = resource_name
            return True
        except Exception as e:
            self.instr = None
            self._resource = None
            _OPEN_PORTS.pop(resource_name, None)
            self.last_error = f"Bağlanamadı: {e}"
            return False

    def _reopen(self) -> bool:
        """Oturum bozulursa ayni kaynagi yeniden acar.
        Kilit altinda yapilir: baska thread instr'i kullanirken kapatilmaz."""
        if not self._resource:
            return False
        with self._lock:
            try:
                if not self.connect(self._resource):
                    return False
                try:
                    self.instr.clear()
                except Exception:
                    pass
                return True
            except Exception:
                return False

    def disconnect(self):
        if self._resource:
            with _registry_lock:
                if _OPEN_PORTS.get(self._resource) is self:
                    _OPEN_PORTS.pop(self._resource, None)
        if self.instr is not None:
            # Cihazi transfer durumundan cikar (yarim kalan okuma USBTMC'yi kilitlar)
            try:
                self.instr.clear()
            except Exception:
                pass
            try:
                self.instr.close()
            except Exception:
                pass
            self.instr = None
        if self.rm is not None:
            try:
                self.rm.close()
            except Exception:
                pass
            self.rm = None

    @property
    def is_connected(self) -> bool:
        return self.instr is not None

    def write(self, command: str):
        with self._lock:
            try:
                self.instr.write(command)
                return
            except Exception:
                pass
        if self._reopen():
            try:
                self.instr.write(command)
            except Exception:
                pass

    def query(self, command: str) -> str:
        with self._lock:
            try:
                return self.instr.query(command).strip()
            except Exception:
                pass
            # buffer'da yarim kalan veri olabilir; temizleyip bir daha dene
            try:
                self.instr.clear()
                return self.instr.query(command).strip()
            except Exception:
                pass
        # oturum bozulmus olabilir; yeniden acip bir kez daha dene
        if self._reopen():
            try:
                return self.instr.query(command).strip()
            except Exception:
                return ""
        return ""

    def query_binary(self, command: str) -> bytes:
        """Cevabı raw binary olarak okur (ekran görüntüsü vb.)."""
        with self._lock:
            try:
                self.instr.chunk_size = 10 * 1024 * 1024  # 1 MB'lik BMP 20KB'lik parçalarla çok yavaş
                self.instr.timeout = 10000
                self.instr.write(command)
                return self.instr.read_raw()
            except Exception:
                pass
        if self._reopen():
            try:
                self.instr.chunk_size = 10 * 1024 * 1024
                self.instr.timeout = 10000
                self.instr.write(command)
                return self.instr.read_raw()
            except Exception:
                return b""
        return b""

