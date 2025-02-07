



def log_output(message,output_queue):
    # Ensure the message ends with a newline
    if not message.endswith("\n"):
        message += "\n"
    # If an output queue is provided, send the message there;
    # otherwise, print to the console.
    if output_queue:
        output_queue.put(message)
    else:
        print(message, end="")  # print adds no extra newline since we already did

