from email.policy import default
import logging
import sys
from time import sleep, perf_counter
from tracemalloc import start
import numpy as np
from pathlib import Path
from datetime import datetime
from PyQt5.QtCore import QLocale
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.display.Qt import QtGui
from pymeasure.display.windows import ManagedWindow

from pymeasure.experiment import (
    Procedure,
    FloatParameter,
    unique_filename,
    Results,
    BooleanParameter,
    Parameter,
)

log = logging.getLogger("")
log.addHandler(logging.NullHandler())


class BubblePlating(Procedure):
    measure_voltage = BooleanParameter("Measure Output Voltage", default=False)
    open_circuit = BooleanParameter("Open Circuit during Pause?", default=False)

    max_current = FloatParameter("Compliance Current", units="mA", default=500)

    start_voltage = FloatParameter("Start Voltage", units="V", default=0)
    end_voltage = FloatParameter("End Voltage", units="V", default=2)
    step_size = FloatParameter("Voltage Step Size", units="V", default=0.05)

    plating_time = FloatParameter("Plating Time per Voltage", units="s", default=10)
    down_time = FloatParameter("Down Time", units="s", default=10)

    DATA_COLUMNS = ["Time (s)", "Current (A)", "Voltage (V)"]

    def startup(self):
        log.info("Setting up instruments")
        self.time_offset = 0
        self.meter = Keithley2400("GPIB0::24::INSTR")
        self.meter.reset()
        self.meter.use_rear_terminals()
        if self.open_circuit:
            self.meter.output_off_state = "HIMP"
        self.meter.apply_voltage()
        self.meter.source_delay = 0
        self.meter.measure_concurent_functions = False
        speedcoms = [
            ":SYSTEM:AZER:STAT OFF",
            ":SENS:FUNC:OFF:ALL",
            ":SENS:FUNC 'CURR'",
            ":FORM:ELEM CURR",
            ":SENSE:AVER:STAT OFF",
            # ":SYSTEM:TIME:RESET:AUTO OFF",
            ":DISP:ENAB OFF",
        ]
        if self.measure_voltage:
            self.meter.measure_concurent_functions = True
            speedcoms = [
                ":SYSTEM:AZER:STAT OFF",
                ":SENS:FUNC:OFF:ALL",
                ":SENS:FUNC 'VOLT','CURR'",
                ":FORM:ELEM VOLT,CURR",
                ":SENSE:AVER:STAT OFF",
                # ":SYSTEM:TIME:RESET:AUTO ON",
                ":DISP:ENAB OFF",
            ]
        for c in speedcoms:
            self.meter.write(c)
            sleep(0.1)
        self.meter.compliance_current = self.max_current / 1000
        self.meter.current_range = self.max_current / 1000

        self.meter.current_nplc = 0.01
        self.meter.voltage_nplc = 0.01
        sleep(2)

    def execute(self):
        log.info("Starting Bubble Plating")
        # current_list = list()
        # current_time = list()
        # voltage_list = list()
        plating_voltages = np.arange(
            self.start_voltage, self.end_voltage + self.step_size, self.step_size
        )
        total_time = (self.plating_time + self.down_time) * len(
            plating_voltages
        ) - self.down_time
        start_time = perf_counter()
        for volt in plating_voltages:
            volt = round(volt, 2)
            self.meter.source_voltage = volt
            self.meter.enable_source()
            cur_volt_time = perf_counter()
            cur_volt_start_diff = cur_volt_time - start_time
            while True:
                cur_time = perf_counter() - cur_volt_time
                messt1 = perf_counter()
                if self.measure_voltage:
                    mvolt, mcurrent = self.meter.current
                else:
                    mcurrent = self.meter.current
                    mvolt = self.voltage
                messt2 = perf_counter()
                cur_time = perf_counter() - cur_volt_time - (messt2 - messt1) / 2
                # current_time.append(cur_time)
                # voltage_list.append(mvolt)
                # current_list.append(mcurrent)
                data = {
                    "Time (s)": cur_time + cur_volt_start_diff,
                    "Current (A)": mcurrent,
                    "Voltage (V)": mvolt,
                    # "Charge (mAs)": charge,
                }
                self.emit("results", data)
                self.emit("progress", 100 * cur_time / total_time)
                if self.should_stop():
                    log.warning("Catch stop command in procedure")
                    break
                if cur_time >= self.plating_time:
                    # print(len(current_list))
                    break

            pause_start = perf_counter()
            if self.open_circuit:
                self.meter.disable_source()
                while perf_counter() - pause_start < self.down_time:
                    sleep(1)
                    cur_volt_time = perf_counter()
                    cur_volt_start_diff = cur_volt_time - start_time
                    while True:
                        cur_time = perf_counter() - cur_volt_time
                        messt1 = perf_counter()
                        if self.measure_voltage:
                            mvolt, mcurrent = self.meter.current
                        else:
                            mcurrent = self.meter.current
                            mvolt = self.voltage
                        messt2 = perf_counter()
                        cur_time = (
                            perf_counter() - cur_volt_time - (messt2 - messt1) / 2
                        )
                        data = {
                            "Time (s)": cur_time + cur_volt_start_diff,
                            "Current (A)": mcurrent,
                            "Voltage (V)": mvolt,
                        }
                        self.emit("results", data)
                        self.emit("progress", 100 * cur_time / total_time)
                        if self.should_stop():
                            log.warning("Catch stop command in procedure")
                            break
                        if cur_time >= self.down_time:
                            # print(len(current_list))
                            break
            else:
                self.meter.source_voltage = 0

            log.info(f"{volt} done")

    def shutdown(self):
        self.measure_open_voltage()
        self.meter.write(":DISP:ENAB ON")
        self.meter.shutdown()
        log.info("Finished")


class MainWindow(ManagedWindow):
    def __init__(self):
        super().__init__(
            procedure_class=BubblePlating,
            inputs=[
                "measure_voltage",
                "open_circuit",
                "max_current",
                "start_voltage",
                "end_voltage",
                "step_size",
                "plating_time",
                "down_time",
            ],
            displays=[
                "measure_voltage",
                "open_circuit",
                "max_current",
                "start_voltage",
                "end_voltage",
                "step_size",
                "plating_time",
                "down_time",
            ],
            x_axis="Time (s)",
            y_axis="Current (A)",
            num_of_points=10000,
            directory_input=True,
        )
        self.setWindowTitle("Bubble Plating")
        self.plot_widget.plot.showGrid(x=True, y=True)
        self.directory = r"C:/"
        self.sample_name = datetime.today().strftime("%Y%m%d")

    def queue(self):
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
        filename = unique_filename(directory, prefix="BP")
        procedure = self.make_procedure()
        results = Results(procedure, filename)
        experiment = self.new_experiment(results)

        self.manager.queue(experiment)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
