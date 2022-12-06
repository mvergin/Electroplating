import pyvisa

rm = pyvisa.ResourceManager()
print(rm.list_resources())
inst = rm.open_resource(rm.list_resources()[2])
print(inst.query("*IDN?"))
