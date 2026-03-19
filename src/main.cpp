#include <Arduino.h>
#include <avr/interrupt.h>

// Pins (must be global because ISR uses them)
const int pulsePin = A0;
const int blinkPin = 13;

// Shared variables used in ISR
volatile int BPM = 0;
volatile int Signal = 0;
volatile int IBI = 600;
volatile bool Pulse = false;
volatile bool QS = false;

static bool serialVisual = false;

volatile int rate[10];
volatile unsigned long sampleCounter = 0;
volatile unsigned long lastBeatTime = 0;
volatile int P = 512;
volatile int T = 512;
volatile int thresh = 525;
volatile int amp = 100;
volatile bool firstBeat = true;
volatile bool secondBeat = false;  

// Function prototypes
void interruptSetup();
void serialOutput();
void serialOutputWhenBeatHappens();
void arduinoSerialMonitorVisual(char symbol, int data);
void sendDataToSerial(char symbol, int data);

void setup() {
  pinMode(blinkPin, OUTPUT);
  Serial.begin(115200);
  interruptSetup();
}

void loop() {
  serialOutput();

  if (QS) {
    serialOutputWhenBeatHappens();
    QS = false;
  }

  delay(20);
}

void interruptSetup() {
  TCCR2A = 0x02;   // CTC mode
  TCCR2B = 0x06;   // prescaler 256
  OCR2A  = 124;    // ~2ms tick on 16MHz AVR
  TIMSK2 = 0x02;   // enable compare match A interrupt
  sei();
}

void serialOutput() {
  if (serialVisual) {
    arduinoSerialMonitorVisual('-', Signal);
  } else {
    sendDataToSerial('S', Signal);
  }
}

void serialOutputWhenBeatHappens() {
  if (serialVisual) {
    Serial.print("Heart-Beat Found  BPM: ");
    Serial.println(BPM);
  } else {
    sendDataToSerial('B', BPM);
    sendDataToSerial('Q', IBI);
  }
}

void arduinoSerialMonitorVisual(char symbol, int data) {
  int range = map(data, 0, 1023, 0, 11);
  Serial.print(symbol);
  while (range-- > 0) Serial.print(symbol);
  Serial.println();
}

void sendDataToSerial(char symbol, int data) {
  Serial.print(symbol);
  Serial.println(data);
}

ISR(TIMER2_COMPA_vect) {
  Signal = analogRead(pulsePin);
  sampleCounter += 2;

  int N = (int)(sampleCounter - lastBeatTime);

  if (Signal < thresh && N > (IBI / 5) * 3) {
    if (Signal < T) T = Signal;
  }

  if (Signal > thresh && Signal > P) {
    P = Signal;
  }

  if (N > 250) {
    if (Signal > thresh && !Pulse && N > (IBI / 5) * 3) {
      Pulse = true;
      digitalWrite(blinkPin, HIGH);

      IBI = (int)(sampleCounter - lastBeatTime);
      lastBeatTime = sampleCounter;

      if (secondBeat) {
        secondBeat = false;
        for (int i = 0; i < 10; i++) rate[i] = IBI;
      }

      if (firstBeat) {
        firstBeat = false;
        secondBeat = true;
        return;
      }

      word runningTotal = 0;
      for (int i = 0; i < 9; i++) {
        rate[i] = rate[i + 1];
        runningTotal += rate[i];
      }

      rate[9] = IBI;
      runningTotal += rate[9];
      runningTotal /= 10;

      BPM = 60000 / runningTotal;
      QS = true;
    }
  }

  if (Signal < thresh && Pulse) {
    digitalWrite(blinkPin, LOW);
    Pulse = false;

    amp = P - T;
    thresh = amp / 2 + T;
    P = thresh;
    T = thresh;
  }

  if (N > 2500) {
    thresh = 512;
    P = 512;
    T = 512;
    lastBeatTime = sampleCounter;
    firstBeat = true;
    secondBeat = false;
  }
}
