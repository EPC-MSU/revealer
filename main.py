from tkinter import *
from tkinter import ttk


root = Tk()
root.title("Revealer 2")
root.minsize(150, 100)

mainframe = ttk.Frame(root, padding="3 3 12 12")
mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)


root.mainloop()
