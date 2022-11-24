"""

"""

from email.policy import default
import logging
import sys
import tempfile
from time import sleep, perf_counter
from matplotlib import pyplot as plt
import numpy as np
import random
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.display.Qt import QtGui
from PyQt5.QtCore import QLocale
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import (
    Procedure,
    FloatParameter,
    unique_filename,
    Results,
    BooleanParameter,
    Parameter,
)
import statistics

log = logging.getLogger("")
log.addHandler(logging.NullHandler())


class Electroplating(Procedure):
    delay_time = FloatParameter("Delay Time", units="ms", default=1)
    total_time = FloatParameter("Total Time", units="s", default=10)
    # eta = Parameter("ETA")
    # max_current = FloatParameter('Maximum Current', units='mA', default=10)
    # min_current = FloatParameter('Minimum Current', units='mA', default=-10)
    # current_step = FloatParameter('Current Step', units='mA', default=0.1)
    # delay = FloatParametescar('Delay Time', units='ms', default=20)
    # voltage_range = FloatParameter('Voltage Range', units='V', default=10)

    DATA_COLUMNS = ["Time (s)", "Current (A)", "Voltage (V)", "Charge (C)"]

    def startup(self):
        log.info("Setting up instruments")

    def execute(self):
        log.info("Starting pulsed electroplating")
        # :SOUR:VOLT:MODE FIXED
        current_time = list()
        current_list = list()
        voltage_list = list()
        data_get_delta_t = list()
        emit_delta_t = list()
        sendindex = 0
        start_time = perf_counter()
        while True:
            messt1 = perf_counter()
            sleep(self.delay_time / 1000)

            mcurrent = random.random()
            mvolt = random.random()
            messt2 = perf_counter()
            cur_time = perf_counter() - start_time - (messt2 - messt1) / 2
            current_time.append(cur_time)
            current_list.append(mcurrent)
            voltage_list.append(mvolt)
            data_get_delta_t.append(messt2 - messt1)
            # charge = np.trapz(current_list, current_time)
            charge = 1

            # print(charge)
            messt1 = perf_counter()
            if sendindex > 10:
                data = {
                    "Time (s)": cur_time,
                    "Current (A)": mcurrent,
                    "Voltage (V)": mvolt,
                    "Charge (C)": charge,
                }
                self.emit("results", data)
                sendindex = 0
            sendindex += 1
            messt2 = perf_counter()
            emit_delta_t.append(messt2 - messt1)
            # self.emit("progress", 100)
            # print(self.estimate)
            # self.estimate = 1
            if self.should_stop():
                log.warning("Catch stop command in procedure")
                break
            if cur_time >= self.total_time:
                print(len(voltage_list))
                print(
                    f"Data get mean: {statistics.mean(data_get_delta_t):.2e}, std: {statistics.stdev(data_get_delta_t):.2e}"
                )
                print(
                    f"Emit mean: {statistics.mean(emit_delta_t):.2e}, std: {statistics.stdev(emit_delta_t):.2e}"
                )
                print(filename)
                print(self.parameter_values())
                # print(emit_delta_t)
                # with open("timediff.txt", "w") as wr:
                #     for val in timediffs:
                #         wr.write(f"{val}\n")
                # data = {
                #     "Time (s)": cur_time,
                #     "Current (A)": mcurrent,
                #     "Voltage (V)": mvolt,
                # }
                # self.emit("results", data)
                # self.emit(
                #     "progress",
                #     100 - 100 * (self.total_time - cur_time) / self.total_time,
                # )
                break

    def shutdown(self):
        log.info("Finished")


class MainWindow(ManagedWindow):
    def __init__(self):
        super().__init__(
            procedure_class=Electroplating,
            inputs=[
                "delay_time",
                "total_time",
            ],
            displays=["delay_time", "total_time"],
            x_axis="Time (s)",
            y_axis="Current (A)",
            linewidth=1,
        )
        self.setWindowTitle("Electroplating Test")
        self.plot_widget.plot.showGrid(x=True, y=True)
        # print(vars(self.plot_widget.plot.showGrid(x=True, y=True)))

    def queue(self):
        global filename
        filename = tempfile.NamedTemporaryFile().name

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
