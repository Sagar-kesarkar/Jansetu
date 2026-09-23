# JanSetu (जनसेतु) — End-to-End Demonstration Video Script

**Target Duration**: 3:30 to 4:45 Minutes  
**Focus**: Digital Public Infrastructure, Multilingual Voice/Text Grievance Redressal, AI Structuring, and Public Funds Transparency across India.

---

## ⏱ Timed Sequence & Visual Storyboard

| Timestamp | Section | Visual Focus & UI Screen | Spoken Script / Narration |
|---|---|---|---|
| **0:00 – 0:25** | **1. The Problem & Target Communities** | Problem Title Slide & JanSetu Hero Screen | *"Over 600 million Indian citizens face systemic language and digital barriers when reporting basic civic problems like broken roads, dry water supplies, or power outages. Traditional grievance portals require complex typing in English and lack real-time transparency into how public funds are spent. Today, we introduce JanSetu — an AI-powered Digital Public Infrastructure that bridges this divide."* |
| **0:25 – 0:50** | **2. Citizen Intake & Language Selection** | Citizen Web App (`:5173`) | *"A citizen opens the JanSetu portal and selects their preferred language from 13 Indian languages — let's select Hindi. Whether reporting via text or voice, the citizen simply speaks naturally in their mother tongue: 'हमारे गाँव शिवाजी नगर, पुणे में पिछले 3 दिन से पानी की पाइपलाइन टूटी हुई है।' Notice the real-time speech transcription and optional photograph upload for physical evidence."* |
| **0:50 – 1:25** | **3. Gemini Structuring & Location Verification** | Processing Indicator & Live API Response | *"Behind the scenes, Google Gemini parses the broken native dialect. It extracts the sector as Drinking Water Supply, estimates urgency at 3/5, and validates the location against India's LGD directory and 542 geographic aliases. If the location was missing, JanSetu immediately prompts for clarification in Hindi before generating a ticket. Here, the location resolves to Shivaji Nagar, Pune, Maharashtra."* |
| **1:25 – 1:55** | **4. Token Issuance & Multi-Issue Splitting** | Token Receipt Modal (`JS-72G8-PEHC`) | *"The platform issues a unique, privacy-preserving tracking token — JS-72G8-PEHC. If the citizen had mentioned multiple distinct issues in a single sentence — such as a broken road and damaged school roof — JanSetu automatically splits them into distinct dockets with individual tracking tokens."* |
| **1:55 – 2:30** | **5. Officials Console & Casework Desk** | Officials Console (`:5174`) | *"Switching to the Officials Console, we see the structured grievance instantly appear in the caseworker queue via live Server-Sent Events. The official sees a clean, zero-PII summary, extracted urgency, ward-level geocoding, and photo evidence. The officer drafts a response: 'Repair crew dispatched. Restoration expected within 6 hours.' Gemini automatically translates this reply into Hindi on the fly."* |
| **2:30 – 3:05** | **6. Real-Time Citizen Tracking & Audit History** | Track Request Screen (`:5173`) | *"Returning to the citizen portal, the citizen inputs their token. They see their status update in real-time to 'Work in Progress', read the official response translated into their language, and inspect the chronological audit history without needing an account, password, or OTP."* |
| **3:05 – 3:40** | **7. Omnichannel Access: WhatsApp, SMS & IVR** | Telephony Handsets & IVR Simulator | *"JanSetu is truly omnichannel. On feature phones, citizens dial our IVR telephony simulator, selecting languages and recording voice notes. On WhatsApp and SMS, our conversational state machine guides citizens through reporting and provides instant token confirmations."* *(Note: Live handset simulator demonstrated; live Exotel/Meta webhooks available when provider credentials configured).* |
| **3:40 – 4:15** | **8. Authoritative Public Funds Transparency** | Public Funds Dashboard (`:5173` / `:5174`) | *"Citizens and officials can also inspect authoritative government budget data. JanSetu tracks Allocations, Releases, and Expenditures, applying strict stage precedence where Revised Estimates supersede Budget Estimates without double-counting. We can see live district comparisons, utilization rates, and data availability flags."* |
| **4:15 – 4:35** | **9. India-Wide Scalability & Conclusion** | Scalability Map & Closing Summary | *"Built with open APIs, LGD compatibility, and strict privacy guarantees, JanSetu is ready to scale across all 28 states and union territories. JanSetu: bridging citizens and government with equitable AI."* |

---

## 🎬 Recording & Presentation Tips
1. **Resolution**: 1920x1080 (1080p), 60fps.
2. **Audio**: Clean microphone audio with clear narration.
3. **Pacing**: Steady navigation through Citizen Intake -> Officials Reply -> Citizen Tracking -> Public Funds.
