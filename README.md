# ServerlessAIProject
Uses jupyter notebook magic commands to spin up google cloud vm and run cell or line code on new vm before returning output back to user

sshCommands.py -> has the code that spins up the vm and interacts with google cloud api

magic/runvm.py -> has the code for the magic command 

%%runvm -> runs all the code in the cell on the vm

%runvm -> runs the code of the line on the vm
