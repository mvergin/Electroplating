import logging
import sys
from time import sleep, perf_counter
from tracemalloc import start
import numpy as np
from pathlib import Path
from datetime import datetime
from PyQt5.QtCore import QLocale
from pymeasure.instruments.keithley import Keithley2600

from pymeasure.display.Qt import QtWidgets
from pymeasure.display.windows import ManagedWindow
import pyvisa

rm = pyvisa.ResourceManager()
from pymeasure.experiment import (
    Procedure,
    FloatParameter,
    unique_filename,
    Results,
    BooleanParameter,
    ListParameter,
    Parameter,
)

FARADAY = 96485.332123
material_dict = {
    "copper": {
        "ele_per_depos": 1,
        "plating_eff": 0.99,
        "density": 8.96,
        "atom_mass": 63.546,
    }
}


log = logging.getLogger("")
log.addHandler(logging.NullHandler())


def calc_charge_plating(nw_dia, nw_height, photo_height, growth_area):
    faraday_const = 96485.332
    eff_plating = 0.99
    cu_elecs = 2
    cu_density = 8.96
    cu_mass = 63.546
    wire_area = self.nw_dia * self.nw_dia * (np.pi / 4) * 1e-9 * 1e-9
    fillfactor = wire_area * self.nw_dens * 1 / (0.01 * 0.01)
    # photo height in um divide by 10k for cm, growth area in mm2 divide by 1000 for cm2
    stamp_vol = (self.photo_height / 10000) * (self.growth_area / 100)
    if not self.photo_calc:
        stamp_vol = 0
    wire_vol = (self.growth_area / 100) * (self.nw_height / 10000) * fillfactor
    vol_weight = (stamp_vol + wire_vol) * cu_density
    cu_atoms = vol_weight / cu_mass
    ele_mol = cu_atoms * cu_elecs
    self.max_charge = ele_mol * faraday_const * eff_plating
    return 1


class Electroplating(Procedure):
    material_sel = ListParameter(
        "Material Selection",
        [k for k in material_dict.keys()],
        default="copper",
    )
    pulse = BooleanParameter("Pulse Mode", default=True)
    # measure_voltage = BooleanParameter("Measure Output Voltage", default=False)
    charge_stop = BooleanParameter(
        "Charge Stop Mode",
        default=False,
        group_by="nw_charge_stop",
        group_condition=False,
    )
    nw_charge_stop = BooleanParameter(
        "Nanowire Charge Stop",
        default=False,
        group_by="charge_stop",
        group_condition=False,
    )
    photo_calc = BooleanParameter(
        "Photoresist",
        default=False,
    )
    max_charge = FloatParameter(
        "Max Charge",
        units="mC",
        default=10000,
        group_by="charge_stop",
        group_condition=True,
    )
    nw_dia = FloatParameter(
        "Pore Diameter",
        units="nm",
        default=400,
        group_by="nw_charge_stop",
        group_condition=True,
    )
    nw_dens = FloatParameter(
        "Pore Density",
        default=1.5e8,
        group_by="nw_charge_stop",
        group_condition=True,
    )
    growth_area = FloatParameter(
        "Growth Area",
        units="mm2",
        default=39 * 39 * np.pi / 4,
        group_by="nw_charge_stop",
        group_condition=True,
    )
    nw_height = FloatParameter(
        "NW Height",
        units="um",
        default=5,
        group_by="nw_charge_stop",
        group_condition=True,
    )
    photo_height = FloatParameter(
        "Photoresist Height",
        units="um",
        default=1.2,
        group_by="photo_calc",
        group_condition=True,
    )
    voltage = FloatParameter(
        "Applied Voltage",
        units="V",
        default=0.5,
        group_by="pulse",
        group_condition=False,
    )

    max_current = FloatParameter("Compliance Current", units="mA", default=500)
    total_time = FloatParameter("Total Time", units="s", default=10)
    pulse_width = FloatParameter(
        "Pulse Width", units="ms", default="40", group_by="pulse"
    )
    pulse_height = FloatParameter(
        "Pulse Height", units="V", default=0.1, group_by="pulse"
    )
    pause_width = FloatParameter(
        "Pause Width", units="ms", default="40", group_by="pulse"
    )
    pause_height = FloatParameter(
        "Pause Height", units="V", default=0.05, group_by="pulse"
    )

    DATA_COLUMNS = ["Time (s)", "Current (mA)", "Voltage (V)", "Charge (mC)"]

    def measure_open_voltage(self):
        self.meter.reset()
        self.meter.use_front_terminals()
        # self.meter.output_off_state = "HIMP"
        self.meter.apply_current()
        coms = [
            ":SOUR:FUNC CURR",
            ":SENS:FUNC 'VOLT'",
            ":SOUR:CURR:RANG MIN",
            ":SOUR:CURR:LEV 0",
            ":SOUR:VOLT:PROT PROT20",
            ":SENS:VOLT:RANG:AUTO ON",
            # ":FORM:ELEM VOLT",
        ]
        for c in coms:
            # print(f"writing {c}")
            self.meter.write(c)
            sleep(0.1)
        self.meter.enable_source()
        start_time = perf_counter()
        while perf_counter() - start_time < 2:
            messt1 = perf_counter()
            mvolt = self.meter.voltage
            messt2 = perf_counter()
            cur_time = (
                perf_counter() - start_time - (messt2 - messt1) / 2 + self.time_offset
            )
            data = {
                "Time (s)": cur_time,
                "Current (mA)": 0,
                "Voltage (V)": mvolt,
                "Charge (mC)": 0,
            }
            self.emit("results", data)
        self.time_offset = perf_counter() - start_time
        self.meter.disable_source()

    def startup(self):
        log.info("Setting up instruments")
        if self.nw_charge_stop:
            self.charge_stop = True
            faraday_const = 96485.332
            eff_plating = 0.99
            cu_elecs = 2
            cu_density = 8.96
            cu_mass = 63.546
            wire_area = self.nw_dia * self.nw_dia * (np.pi / 4) * 1e-9 * 1e-9
            fillfactor = wire_area * self.nw_dens * 1 / (0.01 * 0.01)
            # photo height in um divide by 10k for cm, growth area in mm2 divide by 1000 for cm2
            stamp_vol = (self.photo_height / 10000) * (self.growth_area / 100)
            if not self.photo_calc:
                stamp_vol = 0
            wire_vol = (self.growth_area / 100) * (self.nw_height / 10000) * fillfactor
            vol_weight = (stamp_vol + wire_vol) * cu_density
            cu_atoms = vol_weight / cu_mass
            ele_mol = cu_atoms * cu_elecs
            self.max_charge = ele_mol * faraday_const * eff_plating
            log.info(f"{self.max_charge=}")
            print(f"{wire_area=}")
            print(f"{fillfactor=}")
            print(f"{stamp_vol=}")
            print(f"{wire_vol=}")
            print(f"{cu_atoms=}")
            print(f"{self.max_charge=}")
        self.time_offset = 0
        raise NotImplementedError
        # self.meter = Keithley2400("GPIB0::24::INSTR")
        self.meter = Keithley2600(rm.list_resources()[0])
        # self.measure_open_voltage()
        # self.meter.reset()
        # self.meter.use_front_terminals()
        # self.meter.output_off_state = "HIMP"
        # self.meter.apply_voltage()

        # self.meter.source_delay = 0
        # self.meter.measure_concurent_functions = False
        # ??? :SOUR:VOLT:MODE FIXED
        speedcoms = [
            "CURR:AZER OFF",
            # ":SENS:AZER:STAT OFF",
            # ":SENS:FUNC:OFF:ALL",
            ":SENS:FUNC 'CURR'",
            # ":FORM:ELEM CURR",
            # ":SENSE:AVER:STAT OFF",
            # ":SYSTEM:TIME:RESET:AUTO OFF",
            ":DISP:LIGH:STAT OFF",
        ]
        if self.measure_voltage:
            # self.meter.measure_concurent_functions = True
            speedcoms = [
                # "CURR:AZER OFF",
                # ":SENS:AZER:STAT OFF",
                # ":SENS:FUNC:OFF:ALL",
                ":SENS:FUNC 'CURR'",
                # ":FORM:ELEM VOLT,CURR",
                # ":SENSE:AVER:STAT OFF",
                # ":SYSTEM:TIME:RESET:AUTO ON",
                ":DISP:LIGH:STAT OFF",
            ]
        for c in speedcoms:
            # print(f"writing {c}")
            # self.meter.write(mC)
            sleep(0.1)

        # self.meter.compliance_current = self.max_current / 1000
        # self.meter.current_range = self.max_current / 1000
        self.meter.ChA.compliance_current = self.max_current / 1000
        # self.meter.ChA.compliance_current = self.max_current / 1000
        self.meter.ChA.write("measure.nplc = 0.001")
        self.meter.ChA.write("measure.autozero = smua.AUTOZERO_ONCE")
        self.meter.ChA.write("measure.delay = 0")
        self.meter.ChA.write("source.delay = 0")
        # self.meter.current_nplc = 0.01
        # self.meter.voltage_nplc = 0.01

        sleep(2)

    def execute(self):
        if self.nw_charge_stop:
            self.charge_stop = True
            faraday_const = 96485.332
            eff_plating = 0.99
            cu_elecs = 2
            cu_density = 8.96
            cu_mass = 63.546
            wire_area = self.nw_dia * self.nw_dia * np.pi / 4
            fillfactor = wire_area * self.nw_dens * 1 / (0.01 * 0.01)
            stamp_vol = self.photo_height * self.growth_area
            wire_vol = self.growth_area * self.nw_height * fillfactor
            vol_weight = (stamp_vol + wire_vol) * cu_density
            cu_atoms = vol_weight / cu_mass
            ele_mol = cu_atoms * cu_elecs
            self.max_charge = ele_mol * faraday_const * eff_plating
            log.info(f"{self.max_charge=}")
        if self.pulse:
            current_list = list()
            current_time = list()
            voltage_list = list()
            charge_1 = 0
            mcurrent_1 = 0
            mtime_1 = 0
            self.pulse_width /= 1000
            self.pause_width /= 1000
            PULSE = False
            log.info("Starting pulsed electroplating")

            self.meter.ChA.source_voltage = self.pause_height
            # self.meter.ChA.source_voltage = self.voltage
            self.meter.ChA.source_output = "ON"
            start_time = perf_counter()
            cur_pulse_time = perf_counter()
            while True:
                cur_time = perf_counter() - start_time
                if PULSE:
                    if perf_counter() >= cur_pulse_time + self.pulse_width:
                        messt1 = perf_counter()
                        self.meter.ChA.source_voltage = self.pause_height
                        messt2 = perf_counter()
                        cur_pulse_time = perf_counter() - (messt2 - messt1) / 2
                        PULSE = False
                else:
                    if perf_counter() >= cur_pulse_time + self.pause_width:
                        messt1 = perf_counter()
                        self.meter.ChA.source_voltage = self.pulse_height
                        messt2 = perf_counter()
                        cur_pulse_time = perf_counter() - (messt2 - messt1) / 2
                        PULSE = True
                messt1 = perf_counter()
                if self.measure_voltage:
                    mvolt, mcurrent = self.meter.current
                else:
                    mcurrent = self.meter.ChA.current
                    mvolt = self.voltage
                mcurrent *= 1000
                messt2 = perf_counter()
                cur_time = perf_counter() - start_time - (messt2 - messt1) / 2
                current_time.append(cur_time)
                voltage_list.append(mvolt)
                current_list.append(mcurrent)
                charge = charge_1 + np.trapz(
                    [mcurrent_1, mcurrent], [mtime_1, cur_time]
                )
                charge_1 = charge
                mcurrent_1 = mcurrent
                mtime_1 = cur_time
                data = {
                    "Time (s)": cur_time + self.time_offset,
                    "Current (mA)": mcurrent,
                    "Voltage (V)": mvolt,
                    "Charge (mC)": charge,
                }
                self.emit("results", data)
                self.emit("progress", 100 * cur_time / self.total_time)
                if self.should_stop():
                    log.warning("Catch stop command in procedure")
                    break
                if self.charge_stop and charge >= self.max_charge:
                    log.info("Maximum Charge reached")
                    break
                if cur_time >= self.total_time:
                    print(len(current_list))
                    break
        else:
            current_list = list()
            current_time = list()
            voltage_list = list()
            charge_1 = 0
            mcurrent_1 = 0
            mtime_1 = 0
            log.info("Starting constant electroplating")

            self.meter.ChA.source_voltage = self.voltage
            self.meter.ChA.source_output = "ON"
            start_time = perf_counter()
            while True:
                messt1 = perf_counter()
                if self.measure_voltage:
                    mvolt, mcurrent = self.meter.current

                else:
                    mcurrent = self.meter.ChA.current
                    mvolt = self.voltage
                mcurrent *= 1000
                messt2 = perf_counter()
                cur_time = perf_counter() - start_time - (messt2 - messt1) / 2
                current_time.append(cur_time)
                current_list.append(mcurrent)
                voltage_list.append(mvolt)
                charge = charge_1 + np.trapz(
                    [mcurrent_1, mcurrent], [mtime_1, cur_time]
                )
                charge_1 = charge
                mcurrent_1 = mcurrent
                mtime_1 = cur_time
                data = {
                    "Time (s)": cur_time + self.time_offset,
                    "Current (mA)": mcurrent,
                    "Voltage (V)": mvolt,
                    "Charge (mC)": charge,
                }
                self.emit("results", data)
                self.emit("progress", 100 * cur_time / self.total_time)
                if self.should_stop():
                    log.warning("Catch stop command in procedure")
                    break
                if self.charge_stop and charge >= self.max_charge:
                    log.info("Maximum Charge reached")
                    break
                if cur_time >= self.total_time:
                    print(len(current_list))
                    break
        self.time_offset = self.time_offset + cur_time

    def shutdown(self):
        # self.measure_open_voltage()
        # self.meter.write(":DISP:LIGH:STAT ON50",)
        # self.meter.shutdown()
        self.meter.ChA.source_voltage = 0
        self.meter.ChA.source_output = "OFF"
        log.info("Finished")


class MainWindow(ManagedWindow):
    def __init__(self):
        super().__init__(
            procedure_class=Electroplating,
            inputs=[
                # "measure_voltage",
                "charge_stop",
                "nw_charge_stop",
                "max_charge",
                "photo_calc",
                "nw_dia",
                "nw_dens",
                "growth_area",
                "nw_height",
                "photo_height",
                "pulse",
                "max_current",
                "total_time",
                "pulse_width",
                "pulse_height",
                "pause_width",
                "pause_height",
                "voltage",
            ],
            displays=[
                # "measure_voltage",
                "charge_stop",
                "nw_charge_stop",
                "max_charge",
                "photo_calc",
                "nw_dia",
                "nw_dens",
                "growth_area",
                "nw_height",
                "photo_height",
                "pulse",
                "max_current",
                "total_time",
                "pulse_width",
                "pulse_height",
                "pause_width",
                "pause_height",
                "voltage",
            ],
            x_axis="Time (s)",
            y_axis="Current (mA)",
            num_of_points=10000,
            directory_input=True,
        )
        self.setWindowTitle("Electroplating")
        self.plot_widget.plot.showGrid(x=True, y=True)
        self.directory = r"C:/"
        self.sample_name = "EP" + datetime.today().strftime("%Y%m%d")

    def queue(self):
        # print(f"{self.inputs}")
        # directory = "EP_Measurements/"  # Change this to the desired directory
        # print(self.sample_name)
        dic_path = Path(self.directory) / (self.sample_name + "_1")
        counter = 1
        while True:
            if not dic_path.is_dir():
                dic_path.mkdir(parents=True)
                break
            else:
                counter += 1
                dic_path = Path(self.directory) / (self.sample_name + f"_{counter}")

        directory = dic_path
        filename = unique_filename(directory, prefix="EP")
        procedure = self.make_procedure()
        print(procedure)
        results = Results(procedure, filename)
        experiment = self.new_experiment(results)

        self.manager.queue(experiment)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
