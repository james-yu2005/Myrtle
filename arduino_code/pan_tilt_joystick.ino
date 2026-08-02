#include <Servo.h>

Servo panServo;
Servo tiltServo;

const int PAN_PIN = 4;
const int TILT_PIN = 2;

const int JOY_X = A0;
const int JOY_Y = A1;

float panAngle = 45;
float tiltAngle = 90;

const int CENTER_X = 526; 
const int CENTER_Y = 508;  
const int CENTER_DEADZONE = 20;   
const float MAX_SPEED = 3.0;     

void setup() {
  Serial.begin(9600);
  panServo.attach(PAN_PIN);
  tiltServo.attach(TILT_PIN);
  panServo.write(panAngle);
  tiltServo.write(tiltAngle);
}

void loop() {
  int x = analogRead(JOY_X);
  int y = analogRead(JOY_Y);

  int xOffset = x - CENTER_X;
  if (abs(xOffset) > CENTER_DEADZONE) {
    float speed = map(xOffset, -512, 512, MAX_SPEED, -MAX_SPEED);
    panAngle += speed;
    panAngle = constrain(panAngle, 0, 90);
    panServo.write((int)panAngle);
  }

  int yOffset = y - CENTER_Y;
  if (abs(yOffset) > CENTER_DEADZONE) {
    float speed = map(yOffset, -512, 512, MAX_SPEED, -MAX_SPEED);
    tiltAngle += speed;
    tiltAngle = constrain(tiltAngle, 0, 180);
    tiltServo.write((int)tiltAngle);
  }

  Serial.print("Pan: ");
  Serial.print(panAngle);
  Serial.print("  Tilt: ");
  Serial.println(tiltAngle);

  delay(15);
}