import code
import threading
import browsergui
from browsergui import GUI, Paragraph, CodeBlock, Paragraph, run, call_in_background

gui = GUI(Paragraph("""
  Run commands in the REPL.
  As you change `gui`, this page will update.
  Some commands you might run are:
"""))

for sample in ("gui.append(Text('Hiiii!'))",
               "gui.append(Button(callback=(lambda: gui.append(Paragraph('Clicked!')))))"):
  gui.append(CodeBlock(sample))

gui.append(Paragraph("The code for this page is:"))
gui.append(CodeBlock(open(__file__).read()))

def run_repl():
  interpreter = code.InteractiveConsole(locals={'_gui': gui})
  interpreter.runsource('from browsergui import *')
  interpreter.runsource('gui = _gui')
  interpreter.interact(
    banner="""
      Here's an interpreter! You have access to everything in the `browsergui`
      namespace, plus a ready-made GUI named `gui`.
      
      The server startup might print a couple things on top of the prompt -
      don't worry, you're still in the interpreter.
      
      Exiting the interpreter will terminate the program.
    """)

def main():
  call_in_background(run, gui, daemon=True, quiet=True)
  run_repl()
  gui.destroy_streams()


if __name__ == '__main__':
  main()