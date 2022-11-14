import logging
import sys
from time import sleep, perf_counter
import numpy as np
from pathlib import Path
from datetime import datetime
from PyQt5.QtCore import QLocale
from pymeasure.instruments.hp import HP34401A
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


hp_adress = "GPIB0::8::INSTR"


class HP_Measure(Procedure):
    measure_voltage = BooleanParameter(
        "Measure Voltage",
        default=False,
        group_by="measure_current",
        group_condition=False,
    )
    measure_current = BooleanParameter(
        "Measure Current",
        default=False,
        group_by="measure_voltage",
        group_condition=False,
    )
    # open_circuit = FloatParameter("Range Maximum", default=3)

    total_time = FloatParameter("Total Time", units="s", default=60)

    DATA_COLUMNS = ["Time (s)", "Measurement"]

    def startup(self):
        log.info("Setting up instruments")
        self.time_offset = 0
        self.mm = HP34401A(hp_adress)
        self.mm.reset()
        if self.measure_voltage and self.measure_current:
            raise NotImplementedError("Can't do both at the same time")
        if self.measure_voltage:
            ins_str = "VOLT"
        if self.measure_current:
            ins_str = "CURR"
        coms = [
            f"FUNC '{ins_str}:DC'",
            f"{ins_str}:DC:NPLC 0.02",
            "TRIG:DELAY 0",
            "SAMP:COUN 1",
            "ZERO:AUTO OFF",
            # "DISP OFF",
            # f"{ins_str}:DC:RANG MAX",
        ]
        for c in coms:
            self.mm.write(c)
            sleep(0.01)

    def execute(self):
        log.info("Starting Measurement")
        # current_list = list()
        # current_time = list()
        # voltage_list = list()
        start_time = perf_counter()
        while True:
            data = {
                "Time (s)": perf_counter() - start_time,
                "Measurement": self.mm.ask(":READ?").strip()
                # "Charge (mAs)": charge,
            }
            self.emit("results", data)
            self.emit("progress", 100 * perf_counter() - start_time / self.total_time)
            if self.should_stop():
                log.warning("Catch stop command in procedure")
                break
            if perf_counter() - start_time >= self.total_time:
                break

    def shutdown(self):
        self.mm.write(":DISP:ENAB ON")
        self.mm.shutdown()
        log.info("Finished")


class MainWindow(ManagedWindow):
    def __init__(self):
        super().__init__(
            procedure_class=HP_Measure,
            inputs=[
                "measure_voltage",
                "measure_current",
                "total_time",
            ],
            displays=[
                "measure_voltage",
                "measure_current",
                "total_time",
            ],
            x_axis="Time (s)",
            y_axis="Measurement",
            directory_input=True,
        )
        self.setWindowTitle("HP Multimeter")
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
        filename = unique_filename(directory, prefix="HP")
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
