import serial
import time
import threading
import tkinter as tk

arduinoPort = 'COM3'
baudRate = 115200

running = True

darkMode = "#202020"

def readSerial():
    global running
    try:
        m_serial = serial.Serial(arduinoPort, baudRate, timeout=1)
        time.sleep(2)
        updateStatusText(f"mmWave Sensor connected to: {arduinoPort}\n")

        while(running):
            if m_serial.in_waiting > 0:
                rawData = m_serial.readline()
                cleanData = rawData.decode('utf-8').rstrip()
                lowerData = cleanData.lower()

                if "breath rate" in lowerData and "heart rate" in lowerData and "distance" in lowerData:
                    try:
                        parts = cleanData.split("||")
                        for part in parts:
                            partClean = part.strip()
                            partLower = partClean.lower()

                            if "breath" in partLower:
                                root.after(0, lambda p=partClean: breathLabel.config(text=p))
                            elif "heart" in partLower:
                                root.after(0, lambda p=partClean: heartLabel.config(text=p))
                            elif "distance" in partLower:
                                root.after(0, lambda p=partClean: distanceLabel.config(text=p))
                    except Exception as parseError:
                        print(f"Parsing error: {parseError}")
                else:
                    root.after(0, lambda d=cleanData: fallbackLabel.config(text=d))

                    if "breath" in lowerData:
                        root.after(0, lambda d=cleanData: breathLabel.config(text=d))
                    elif "heart" in lowerData:
                        root.after(0, lambda d=cleanData: heartLabel.config(text=d))
                    elif "distance" in lowerData:
                        root.after(0, lambda d=cleanData: distanceLabel.config(text=d))
    except Exception as e:
        print(f"Thread exception: {e}")
        updateStatusText(f"\nConnection or program interrupted...")
    finally:
        if 'm_serial' in locals() and m_serial.isOpen:
            m_serial.close()
            updateStatusText("Serial connection closed.\n")

def updateStatusText(text):
    statusLabel.config(text=text)

def onClosing():
    global running
    running = False
    root.destroy()

root = tk.Tk()
root.title("mmWave Sensor Dashboard")
root.geometry("800x500")

root.configure(bg=darkMode)

label = tk.Label(root, text="mmWave Sensor Dashboard", font=("Helvetica", 20, "bold"), fg="#ffffff", bg=darkMode)
label.pack(pady=15)

distanceLabel = tk.Label(root, text="Distance: --", font=("Segoe UI", 35, "bold"), fg="#46d716", bg=darkMode)
distanceLabel.pack(pady=10)

heartLabel = tk.Label(root, text="Heart Rate: --", font=("Segoe UI", 35, "bold"), fg="#d93025", bg=darkMode)
heartLabel.pack(pady=10)

breathLabel = tk.Label(root, text="Breath Rate: --", font=("Segoe UI", 35, "bold"), fg="#1a73e8", bg=darkMode)
breathLabel.pack(pady=10)

fallbackLabel = tk.Label(root, text="", font=("Segoe UI", 12, "italic"), fg="#808080", bg=darkMode)
fallbackLabel.pack(pady=5)

statusLabel = tk.Label(root, text="Connecting...", font=("Helvetica", 10, "italic"), fg="gray", bg=darkMode)
statusLabel.pack(side="bottom", pady=10)

serialThread = threading.Thread(target=readSerial, daemon=True)
serialThread.start()

root.protocol("WM_DELETE_WINDOW", onClosing)

root.mainloop()