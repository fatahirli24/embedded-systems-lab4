#include <Arduino.h>

// Analog input pins for joystick X and Y axes
int xPin = A0;
int yPin = A1;

// Digital input pin for joystick push button
int buttonPin = 2;

// Variables to store joystick readings
int xVal, yVal, buttonState;

// Output pins for the four direction LEDs
int upLed = 10;
int downLed = 9;
int leftLed = 11;
int rightLed = 6;

// Variables to store PWM brightness for each LED
int upBrightness = 0;
int downBrightness = 0;
int leftBrightness = 0;
int rightBrightness = 0;

void setup() {
  // Start serial communication at 115200 baud
  // This is faster than 9600 and better for real-time visualization
  Serial.begin(115200);

  // Configure joystick pins
  pinMode(xPin, INPUT);
  pinMode(yPin, INPUT);
  pinMode(buttonPin, INPUT_PULLUP);

  // Configure LED pins as outputs
  pinMode(upLed, OUTPUT);
  pinMode(downLed, OUTPUT);
  pinMode(leftLed, OUTPUT);
  pinMode(rightLed, OUTPUT);
}

void loop() {
  // Read joystick X and Y analog values
  xVal = analogRead(xPin);
  yVal = analogRead(yPin);

  // Read joystick push-button state
  buttonState = digitalRead(buttonPin);

  // Reset all LEDs before applying new brightness values
  analogWrite(upLed, 0);
  analogWrite(downLed, 0);
  analogWrite(leftLed, 0);
  analogWrite(rightLed, 0);

  // Convert joystick displacement into PWM brightness values
  upBrightness    = map(yVal, 509, 0,    0, 255);
  downBrightness  = map(yVal, 509, 1023, 0, 255);
  leftBrightness  = map(xVal, 512, 0,    0, 255);
  rightBrightness = map(xVal, 512, 1023, 0, 255);

  // Illuminate the UP LED when joystick is pushed upward
  if (yVal <= 509) analogWrite(upLed, upBrightness);

  // Illuminate the DOWN LED when joystick is pushed downward
  if (yVal >= 509) analogWrite(downLed, downBrightness);

  // Illuminate the RIGHT LED when joystick is pushed right
  if (xVal >= 512) analogWrite(rightLed, rightBrightness);

  // Illuminate the LEFT LED when joystick is pushed left
  if (xVal <= 512) analogWrite(leftLed, leftBrightness);

  // If the joystick button is pressed, turn all LEDs fully on
  if (buttonState == LOW) {
    digitalWrite(upLed, HIGH);
    digitalWrite(downLed, HIGH);
    digitalWrite(leftLed, HIGH);
    digitalWrite(rightLed, HIGH);
  }

  // Send joystick data to the PC in CSV format: x,y,button
  // This format is easy for the Python visualizer to parse
  Serial.print(xVal);
  Serial.print(",");
  Serial.print(yVal);
  Serial.print(",");
  Serial.println(buttonState);

  // Short delay for stable but fast real-time updates
  delay(10);
}
