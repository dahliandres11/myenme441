# Dahlia Andres

# 9/10/25

'''
for x in "enme441":
	print(x, end='...')
'''

'''
myList = [5, -3, 7.4, 6, 4]
for (i,value) in enumerate(myList):
	if value > 5:
		print(i)

'''
'''

a = -10
while a <= 10:
	print(a)
	a += 1

import time
while True:
	print('.')
	time.sleep(0.25)
'''

# Lab 1: Python Loops

# Question 1:
x = 0.5
sumk1 = 0

for k in range(1,6): # k = 1 -> 5?
	eqn = ((-1)**(k-1)) * ((x-1)**(k)) / k
	sumk1 += eqn

print(f"f(0.5) ~= {sumk1:.9f} with 5 terms")

# Question 2:

sumk2 = 0
k = 1
eqn = 1

while abs(eqn) >= 1e-7:
	eqn = ((-1)**(k-1)) * ((x-1)**(k)) / k
	sumk2 += eqn
	k += 1

print(f"f(0.5) ~= {sumk2:.9f} with {k} terms")
'''

while True:
	if int(input('enter number > 10 to end')) > 10:
		break


'''
'''
while 1:
	print('.')

'''
# cd C:\Users\dahli\OneDrive\Attachments\Documents\UMD\FALL 2025\ENME441

# Ctrl C to exit running script!!
