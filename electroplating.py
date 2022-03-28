import logging
import sys
from time import sleep, perf_counter
import numpy as np

from pymeasure.instruments.keithley import Keithley2400
from pymeasure.display.Qt import QtGui
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import (
    Procedure,
    FloatParameter,
    unique_filename,
    Results,
    BooleanParameter,
)

log = logging.getLogger("")
log.addHandler(logging.NullHandler())


class Electroplating(Procedure):
    pulse = BooleanParameter("Pulse Mode", default=False)
    measure_voltage = BooleanParameter("Measure Output Voltage", default=False)
    charge_stop = BooleanParameter("Charge Stop Mode", default=False)
    max_charge = FloatParameter(
        "Max Charge",
        units="mAs",
        default=1000,
        group_by="charge_stop",
        group_condition=True,
    )
    voltage = FloatParameter(
        "Applied Voltage", units="V", default=3, group_by="pulse", group_condition=False
    )

    max_current = FloatParameter("Compliance Current", units="mA", default=500)
    total_time = FloatParameter("Total Time", units="s", default=10)
    pulse_width = FloatParameter(
        "Pulse Width", units="ms", default="10", group_by="pulse"
    )
    pulse_height = FloatParameter(
        "Pulse Height", units="V", default="3", group_by="pulse"
    )
    pause_width = FloatParameter(
        "Pause Width", units="ms", default="40", group_by="pulse"
    )
    pause_height = FloatParameter(
        "Pause Height", units="V", default="0", group_by="pulse"
    )

    DATA_COLUMNS = ["Time (s)", "Current (mA)", "Voltage (V)", "Charge (mAs)"]

    def startup(self):
        log.info("Setting up instruments")
        self.meter = Keithley2400("GPIB0::24::INSTR")
        self.meter.reset()
        self.meter.use_front_terminals()
        self.meter.apply_voltage()

        self.meter.enable_source()
        self.meter.source_delay = 0
        self.meter.measure_concurent_functions = False
        # ??? :SOUR:VOLT:MODE FIXED
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

            self.meter.source_voltage = self.pause_height
            start_time = perf_counter()
            cur_pulse_time = perf_counter()
            while True:
                cur_time = perf_counter() - start_time
                if PULSE:
                    if perf_counter() >= cur_pulse_time + self.pulse_width:
                        messt1 = perf_counter()
                        self.meter.source_voltage = self.pause_height
                        messt2 = perf_counter()
                        cur_pulse_time = perf_counter() - (messt2 - messt1) / 2
                        PULSE = False
                else:
                    if perf_counter() >= cur_pulse_time + self.pause_width:
                        messt1 = perf_counter()
                        self.meter.source_voltage = self.pulse_height
                        messt2 = perf_counter()
                        cur_pulse_time = perf_counter() - (messt2 - messt1) / 2
                        PULSE = True
                messt1 = perf_counter()
                if self.measure_voltage:
                    mvolt, mcurrent = self.meter.current
                else:
                    mcurrent = self.meter.current
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
                    "Time (s)": cur_time,
                    "Current (mA)": mcurrent,
                    "Voltage (V)": mvolt,
                    "Charge (mAs)": charge,
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

            self.meter.source_voltage = self.voltage
            start_time = perf_counter()
            while True:
                messt1 = perf_counter()
                if self.measure_voltage:
                    mvolt, mcurrent = self.meter.current

                else:
                    mcurrent = self.meter.current
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
                    "Time (s)": cur_time,
                    "Current (mA)": mcurrent,
                    "Voltage (V)": mvolt,
                    "Charge (mAs)": charge,
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

    def shutdown(self):
        self.meter.write(":DISP:ENAB ON")
        self.meter.shutdown()
        log.info("Finished")


class MainWindow(ManagedWindow):
    def __init__(self):
        super().__init__(
            procedure_class=Electroplating,
            inputs=[
                "measure_voltage",
                "charge_stop",
                "max_charge",
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
                "measure_voltage",
                "charge_stop",
                "max_charge",
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
        )
        self.setWindowTitle("Electroplating")
        self.plot_widget.plot.showGrid(x=True, y=True)

    def queue(self):
        directory = "EP_Measurements/"  # Change this to the desired directory
        filename = unique_filename(directory, prefix="EP")
        procedure = self.make_procedure()
        results = Results(procedure, filename)
        experiment = self.new_experiment(results)

        self.manager.queue(experiment)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
