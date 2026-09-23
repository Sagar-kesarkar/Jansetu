/**
 * PublicFunds.jsx — Citizen Public Funds & State/District Budget Dashboard
 *
 * Provides transparent, citizen-facing fiscal intelligence:
 * - State and district level budget allocations, releases, and expenditure.
 * - Anti-double-counting stage reconciliation with real anomaly detection.
 * - Active citizen grievance demand comparison against government spending.
 * - Traceable official source provenance with external verification links.
 * - Full multilingual support across 13 Indian languages (defaults to English).
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

import {
  getDistricts,
  getFundsCoverage,
  getFundsDistricts,
  getFundsOverview,
  getFundsSectors,
  getStates,
} from '../api.js'
import { ErrorState, Loading } from '../components/States.jsx'
import { useCapabilities } from '../hooks/useCapabilities.jsx'

// ---- Multilingual Localization Dictionary (13 Indian Languages) ----
const I18N = {
  en: {
    eyebrow: 'Government · Fiscal Transparency',
    title: 'State & District Budget',
    subtitle:
      'Official public fund allocations, treasury releases, and recorded expenditures compared directly against citizen grievances reported on JanSetu.',
    sourceLabel: 'Official Source:',
    viewSource: 'View official source ↗',
    publishedOn: 'Published:',
    lastSynced: 'Last synced:',
    verifiedBadge: 'Verified Official Audit',
    partialBadge: 'Partial Coverage',
    scopeState: 'State budget',
    scopeDistrict: 'District budget',
    filterState: 'State',
    filterDistrict: 'District',
    filterYear: 'Financial Year',
    filterSector: 'Civic Sector',
    allSectors: 'All Sectors',
    kpiAllocated: 'Total Allocated',
    kpiAllocatedSub: 'Approved State Budget',
    kpiReleased: 'Funds Released',
    kpiReleasedSub: 'Treasury to Departments',
    kpiSpent: 'Recorded Expenditure',
    kpiSpentSub: 'Audited / Recorded Payments',
    kpiAvailable: 'Available Released Funds',
    kpiAvailableSub: 'Remaining in Treasury',
    progressTitle: 'Budget Execution & Fund Flow',
    releaseRate: 'Release Rate:',
    utilisationRate: 'Utilisation Rate:',
    legendAllocated: 'Allocated (100%)',
    legendReleased: 'Released',
    legendSpent: 'Spent',
    anomalyWarning:
      'Warning: Recorded expenditure exceeds the released amount. This record requires administrative verification.',
    noDataTitle: 'Data Unavailable',
    noDataBody:
      'No verified official financial data is currently available for this selection. Release or expenditure records have not yet been published by the state finance department for this district.',
    signalsTitle: 'Decision-Support Funding Signals',
    signalsSub: 'Derived comparison between citizen demand volume and financial allocations',
    stateComparisonTitle: 'District Budget Comparison',
    stateComparisonSub: 'Click a district to drill down into localized budget line items',
    activeGrievances: 'active grievances',
    grievancesDonutTitle: 'Citizen Grievances by Sector',
    grievancesDonutSub: 'Share of open public needs reported across channels',
    expenditureDonutTitle: 'Expenditure by Sector',
    expenditureDonutSub: 'Audited public funds spent across civic categories',
    registerTitle: 'Sector Priority & Budget Register',
    colSector: 'Sector',
    colGrievanceShare: 'Grievance Share',
    colAllocated: 'Allocated',
    colReleased: 'Released',
    colSpent: 'Spent',
    colUtilisation: 'Utilisation',
    colAssessment: 'Status',
    viewGrievancesLink: 'View related public grievance data →',
    methodologyTitle: 'Fiscal & Civic Demand Methodology',
    methodologyBody:
      'JanSetu aggregates official state budget publications (Budget Estimates & Revised Estimates) alongside verified public treasury releases and expenditure records. Citizen grievance demand represents live civic needs submitted through IVR, SMS, and WhatsApp. Grievance share is a metric of civic need, not an automatic budget formula.',
  },
  hi: {
    eyebrow: 'सरकारी · वित्तीय पारदर्शिता',
    title: 'राज्य एवं ज़िला बजट',
    subtitle:
      'आधिकारिक सार्वजनिक निधि आवंटन, जारी की गई राशि और वास्तविक व्यय की जनसेतु पर नागरिकों द्वारा दर्ज शिकायतों के साथ पारदर्शी तुलना।',
    sourceLabel: 'आधिकारिक स्रोत:',
    viewSource: 'आधिकारिक स्रोत देखें ↗',
    publishedOn: 'प्रकाशित:',
    lastSynced: 'अंतिम समन्वय:',
    verifiedBadge: 'सत्यापित आधिकारिक ऑडिट',
    partialBadge: 'आंशिक कवरेज',
    scopeState: 'राज्य बजट',
    scopeDistrict: 'ज़िला बजट',
    filterState: 'राज्य',
    filterDistrict: 'ज़िला',
    filterYear: 'वित्तीय वर्ष',
    filterSector: 'नागरिक क्षेत्र',
    allSectors: 'सभी क्षेत्र',
    kpiAllocated: 'कुल आवंटित बजट',
    kpiAllocatedSub: 'स्वीकृत राज्य बजट',
    kpiReleased: 'जारी की गई निधि',
    kpiReleasedSub: 'कोषागार से विभागों को',
    kpiSpent: 'दर्ज व्यय',
    kpiSpentSub: 'ऑडिट किया गया वास्तविक व्यय',
    kpiAvailable: 'उपलब्ध शेष निधि',
    kpiAvailableSub: 'कोषागार में शेष राशि',
    progressTitle: 'बजट क्रियान्वयन एवं निधि प्रवाह',
    releaseRate: 'जारी दर:',
    utilisationRate: 'उपयोग दर:',
    legendAllocated: 'आवंटित (100%)',
    legendReleased: 'जारी',
    legendSpent: 'व्यय',
    anomalyWarning:
      'चेतावनी: दर्ज किया गया व्यय जारी की गई राशि से अधिक है। इस रिकॉर्ड के सत्यापन की आवश्यकता है।',
    noDataTitle: 'डेटा उपलब्ध नहीं है',
    noDataBody:
      'इस चयन के लिए वर्तमान में कोई सत्यापित आधिकारिक वित्तीय डेटा उपलब्ध नहीं है।',
    signalsTitle: 'निर्णय-समर्थन फंडिंग संकेत',
    signalsSub: 'नागरिक मांग और वित्तीय आवंटन के बीच व्युत्पन्न तुलना',
    stateComparisonTitle: 'ज़िला बजट तुलना',
    stateComparisonSub: 'स्थानीय बजट देखने के लिए किसी ज़िले पर क्लिक करें',
    activeGrievances: 'सक्रिय शिकायतें',
    grievancesDonutTitle: 'क्षेत्रवार नागरिक शिकायतें',
    grievancesDonutSub: 'सभी चैनलों पर दर्ज सार्वजनिक जरूरतों का हिस्सा',
    expenditureDonutTitle: 'क्षेत्रवार व्यय',
    expenditureDonutSub: 'नागरिक श्रेणियों में खर्च की गई सार्वजनिक निधि',
    registerTitle: 'क्षेत्रवार प्राथमिकता एवं बजट रजिस्टर',
    colSector: 'क्षेत्र',
    colGrievanceShare: 'शिकायत हिस्सा',
    colAllocated: 'आवंटित',
    colReleased: 'जारी',
    colSpent: 'व्यय',
    colUtilisation: 'उपयोग',
    colAssessment: 'स्थिति',
    viewGrievancesLink: 'संबंधित नागरिक शिकायत डेटा देखें →',
    methodologyTitle: 'वित्तीय एवं नागरिक मांग कार्यप्रणाली',
    methodologyBody:
      'जनसेतु आधिकारिक राज्य बजट प्रकाशनों, स्वीकृत आवंटनों और व्यय रिकॉर्ड को नागरिक शिकायतों के साथ जोड़ता है। शिकायत हिस्सा सार्वजनिक मांग का सूचक है, कोई स्वचालित बजट फॉर्मूला नहीं।',
  },
  mr: {
    eyebrow: 'शासकीय · वित्तीय पारदर्शकता',
    title: 'राज्य व जिल्हा अर्थसंकल्प',
    subtitle:
      'अधिकृत सार्वजनिक निधी वाटप, वितरित निधी आणि प्रत्यक्ष खर्चाची जनसेतूवरील नागरिकांच्या तक्रारींशी थेट तुलना.',
    sourceLabel: 'अधिकृत स्रोत:',
    viewSource: 'अधिकृत स्रोत पहा ↗',
    publishedOn: 'प्रकाशित:',
    lastSynced: 'अंतिम सिंक:',
    verifiedBadge: 'प्रमाणित अधिकृत लेखापरीक्षण',
    partialBadge: 'अंशतः कव्हरेज',
    scopeState: 'राज्य अर्थसंकल्प',
    scopeDistrict: 'जिल्हा अर्थसंकल्प',
    filterState: 'राज्य',
    filterDistrict: 'जिल्हा',
    filterYear: 'आर्थिक वर्ष',
    filterSector: 'नागरी क्षेत्र',
    allSectors: 'सर्व क्षेत्रे',
    kpiAllocated: 'एकूण मंजूर निधी',
    kpiAllocatedSub: 'मंजूर अर्थसंकल्प',
    kpiReleased: 'वितरित निधी',
    kpiReleasedSub: 'तिजोरीतून विभागांना',
    kpiSpent: 'नोंदणीकृत खर्च',
    kpiSpentSub: 'प्रत्यक्ष झालेला खर्च',
    kpiAvailable: 'शिल्लक उपलब्ध निधी',
    kpiAvailableSub: 'तिजोरीत शिल्लक',
    progressTitle: 'अर्थसंकल्प अंमलबजावणी आणि निधी प्रवाह',
    releaseRate: 'वितरण दर:',
    utilisationRate: 'वापर दर:',
    legendAllocated: 'मंजूर (100%)',
    legendReleased: 'वितरित',
    legendSpent: 'खर्च',
    anomalyWarning: 'चेतावणी: प्रत्यक्ष खर्च वितरित निधीपेक्षा जास्त आहे.',
    noDataTitle: 'माहिती उपलब्ध नाही',
    noDataBody: 'या निवडीसाठी अधिकृत वित्तीय माहिती उपलब्ध नाही.',
    signalsTitle: 'निर्णय-सहाय्यक निधी संकेत',
    signalsSub: 'नागरिकांची मागणी आणि निधी वाटपाची थेट तुलना',
    stateComparisonTitle: 'जिल्हा अर्थसंकल्प तुलना',
    stateComparisonSub: 'जिल्हावार माहितीसाठी जिल्ह्यावर क्लिक करा',
    activeGrievances: 'सक्रिय तक्रारी',
    grievancesDonutTitle: 'क्षेत्रनिहाय नागरिक तक्रारी',
    grievancesDonutSub: 'विविध माध्यमांतून आलेल्या तक्रारींची टक्केवारी',
    expenditureDonutTitle: 'क्षेत्रनिहाय खर्च',
    expenditureDonutSub: 'नागरी क्षेत्रात झालेला प्रत्यक्ष खर्च',
    registerTitle: 'क्षेत्रनिहाय प्राधान्य व निधी रजिस्टर',
    colSector: 'क्षेत्र',
    colGrievanceShare: 'तक्रार प्रमाण',
    colAllocated: 'मंजूर',
    colReleased: 'वितरित',
    colSpent: 'खर्च',
    colUtilisation: 'वापर',
    colAssessment: 'स्थिती',
    viewGrievancesLink: 'संबंधित नागरिक तक्रारी पहा →',
    methodologyTitle: 'वित्तीय व नागरी मागणी कार्यपद्धती',
    methodologyBody: 'जनसेतू अधिकृत शासकीय अर्थसंकल्प आणि नागरिकांच्या तक्रारींचे विश्लेषण एकत्र मांडतो.',
  },
  ta: {
    eyebrow: 'அரசு · நிதி வெளிப்படைத்தன்மை',
    title: 'மாநில மற்றும் மாவட்ட வரவு செலவு திட்டம்',
    subtitle: 'அதிகாரப்பூர்வ பொது நிதி ஒதுக்கீடு, விடுவிக்கப்பட்ட நிதி மற்றும் செலவுகள் ஜனசேது புகார்களுடன் ஒப்பிடப்படுகிறது.',
    sourceLabel: 'அதிகாரப்பூர்வ ஆதாரம்:',
    viewSource: 'அதிகாரப்பூர்வ ஆதாரத்தை பார்க்க ↗',
    publishedOn: 'வெளியிடப்பட்டது:',
    lastSynced: 'கடைசி ஒத்திசைவு:',
    verifiedBadge: 'சரிபார்க்கப்பட்ட தணிக்கை',
    partialBadge: 'பகுதி கவரேஜ்',
    scopeState: 'மாநில பட்ஜெட்',
    scopeDistrict: 'மாவட்ட பட்ஜெட்',
    filterState: 'மாநிலம்',
    filterDistrict: 'மாவட்டம்',
    filterYear: 'நிதியாண்டு',
    filterSector: 'துறை',
    allSectors: 'அனைத்து துறைகள்',
    kpiAllocated: 'மொத்த ஒதுக்கீடு',
    kpiAllocatedSub: 'அங்கீகரிக்கப்பட்ட பட்ஜெட்',
    kpiReleased: 'விடுவிக்கப்பட்ட நிதி',
    kpiReleasedSub: 'கருவூலத்திலிருந்து துறைகளுக்கு',
    kpiSpent: 'பதிவு செய்யப்பட்ட செலவு',
    kpiSpentSub: 'தணிக்கை செய்யப்பட்ட செலவு',
    kpiAvailable: 'கிடைக்கும் மீதமுள்ள நிதி',
    kpiAvailableSub: 'கருவூலத்தில் உள்ளது',
    progressTitle: 'பட்ஜெட் செயலாக்கம் & நிதி ஓட்டம்',
    releaseRate: 'விடுவிப்பு விகிதம்:',
    utilisationRate: 'பயன்பாட்டு விகிதம்:',
    legendAllocated: 'ஒதுக்கீடு (100%)',
    legendReleased: 'விடுவிக்கப்பட்டது',
    legendSpent: 'செலவிடப்பட்டது',
    anomalyWarning: 'எச்சரிக்கை: செலவிடப்பட்ட தொகை விடுவிக்கப்பட்ட நிதியை விட அதிகம்.',
    noDataTitle: 'தரவு கிடைக்கவில்லை',
    noDataBody: 'இந்த தேர்வுக்கு சரிபார்க்கப்பட்ட நிதி தரவு தற்போது கிடைக்கவில்லை.',
    signalsTitle: 'முடிவெடுக்கும் நிதி சமிக்ஞைகள்',
    signalsSub: 'பொதுமக்களின் தேவை மற்றும் நிதி ஒதுக்கீட்டின் ஒப்பீடு',
    stateComparisonTitle: 'மாவட்ட பட்ஜெட் ஒப்பீடு',
    stateComparisonSub: 'மாவட்ட வாரியான விவரங்களை அறிய மாவட்டத்தை கிளிக் செய்யவும்',
    activeGrievances: 'செயலில் உள்ள புகார்கள்',
    grievancesDonutTitle: 'துறைவாரியான புகார்கள்',
    grievancesDonutSub: 'பதிவு செய்யப்பட்ட தேவைகளின் சதவீதம்',
    expenditureDonutTitle: 'துறைவாரியான செலவு',
    expenditureDonutSub: 'துறைகளில் செலவிடப்பட்ட பொது நிதி',
    registerTitle: 'துறை முன்னுரிமை & நிதி பதிவேடு',
    colSector: 'துறை',
    colGrievanceShare: 'புகார் பங்கு',
    colAllocated: 'ஒதுக்கீடு',
    colReleased: 'விடுவிப்பு',
    colSpent: 'செலவு',
    colUtilisation: 'பயன்பாடு',
    colAssessment: 'நிலை',
    viewGrievancesLink: 'பொது புகார் தரவை காண்க →',
    methodologyTitle: 'நிதி மற்றும் குடிமக்கள் தேவை வழிமுறை',
    methodologyBody: 'ஜனசேது அரசு பட்ஜெட் மற்றும் குடிமக்கள் புகார்களை வெளிப்படையாக இணைக்கிறது.',
  },
  te: {
    eyebrow: 'ప్రభుత్వం · ఆర్థిక పారదర్శకత',
    title: 'రాష్ట్ర & జిల్లా బడ్జెట్',
    subtitle: 'అధికారిక ప్రజా నిధుల కేటాయింపులు, విడుదలైన నిధులు మరియు ఖర్చులను జనసేతు ఫిర్యాదులతో పోల్చడం.',
    sourceLabel: 'అధికారిక మూలం:',
    viewSource: 'అధికారిక మూలాన్ని చూడండి ↗',
    publishedOn: 'ప్రచురించబడింది:',
    lastSynced: 'చివరి సింక్:',
    verifiedBadge: 'ధృవీకరించబడిన ఆడిట్',
    partialBadge: 'పాక్షిక కవరేజ్',
    scopeState: 'రాష్ట్ర బడ్జెట్',
    scopeDistrict: 'జిల్లా బడ్జెట్',
    filterState: 'రాష్ట్రం',
    filterDistrict: 'జిల్లా',
    filterYear: 'ఆర్థిక సంవత్సరం',
    filterSector: 'రంగం',
    allSectors: 'అన్ని రంగాలు',
    kpiAllocated: 'మొత్తం కేటాయింపు',
    kpiAllocatedSub: 'ఆమోదించబడిన బడ్జెట్',
    kpiReleased: 'విడుదలైన నిధులు',
    kpiReleasedSub: 'ట్రెజరీ నుండి విభాగాలకు',
    kpiSpent: 'నమోదైన ఖర్చు',
    kpiSpentSub: 'ఆడిట్ చేసిన ఖర్చు',
    kpiAvailable: 'అందుబాటులో ఉన్న నిధులు',
    kpiAvailableSub: 'ట్రెజరీలో మిగిలిన నిధులు',
    progressTitle: 'బడ్జెట్ అమలు & నిధుల ప్రవాహం',
    releaseRate: 'విడుదల రేటు:',
    utilisationRate: 'వినియోగ రేటు:',
    legendAllocated: 'కేటాయించినది (100%)',
    legendReleased: 'విడుదలైనది',
    legendSpent: 'ఖర్చు చేసినది',
    anomalyWarning: 'హెచ్చరిక: విడుదల చేసిన మొత్తం కంటే ఎక్కువ ఖర్చు నమోదైంది.',
    noDataTitle: 'డేటా అందుబాటులో లేదు',
    noDataBody: 'ఈ ఎంపికకు అధికారిక ఆర్థిక డేటా ప్రస్తుతం అందుబాటులో లేదు.',
    signalsTitle: 'నిర్ణయ మద్దతు నిధుల సంకేతాలు',
    signalsSub: 'ప్రజా డిమాండ్ మరియు కేటాయింపుల మధ్య పోలిక',
    stateComparisonTitle: 'జిల్లాల బడ్జెట్ పోలిక',
    stateComparisonSub: 'జిల్లా వివరాల కోసం జిల్లాపై క్లిక్ చేయండి',
    activeGrievances: 'క్రియాశీల ఫిర్యాదులు',
    grievancesDonutTitle: 'రంగాల వారీగా ఫిర్యాదులు',
    grievancesDonutSub: 'నమోదైన ప్రజా అవసరాల వాటా',
    expenditureDonutTitle: 'రంగాల వారీగా ఖర్చు',
    expenditureDonutSub: 'వివిధ రంగాలలో ఖర్చు చేసిన ప్రజా నిధులు',
    registerTitle: 'రంగాల ప్రాధాన్యత & నిధుల రిజిస్టర్',
    colSector: 'రంగం',
    colGrievanceShare: 'ఫిర్యాదు వాటా',
    colAllocated: 'కేటాయింపు',
    colReleased: 'విడుదల',
    colSpent: 'ఖర్చు',
    colUtilisation: 'వినియోగం',
    colAssessment: 'స్థితి',
    viewGrievancesLink: 'ప్రజా ఫిర్యాదుల డేటాను చూడండి →',
    methodologyTitle: 'ఆర్థిక మరియు పౌర డిమాండ్ విధానం',
    methodologyBody: 'జనసేతు అధికారిక బడ్జెట్ మరియు పౌరుల సమస్యలను సమగ్రంగా విశ్లేషిస్తుంది.',
  },
  bn: {
    eyebrow: 'সরকারি · আর্থিক স্বচ্ছতা',
    title: 'রাজ্য ও জেলা বাজেট',
    subtitle: 'অফিসিয়াল পাবলিক তহবিল বরাদ্দ, মুক্তিপ্রাপ্ত তহবিল এবং ব্যয়ের সাথে জনসেতু অভিযোগের সরাসরি তুলনা।',
    sourceLabel: 'অফিসিয়াল উৎস:',
    viewSource: 'অফিসিয়াল উৎস দেখুন ↗',
    publishedOn: 'প্রকাশিত:',
    lastSynced: 'সর্বশেষ সিঙ্ক:',
    verifiedBadge: 'যাচাইকৃত অডিট',
    partialBadge: 'আংশিক কভারেজ',
    scopeState: 'রাজ্য বাজেট',
    scopeDistrict: 'জেলা বাজেট',
    filterState: 'রাজ্য',
    filterDistrict: 'জেলা',
    filterYear: 'অর্থবছর',
    filterSector: 'নাগরিক খাত',
    allSectors: 'সকল খাত',
    kpiAllocated: 'মোট বরাদ্দ',
    kpiAllocatedSub: 'অনুমোদিত রাজ্য বাজেট',
    kpiReleased: 'মুক্তিপ্রাপ্ত তহবিল',
    kpiReleasedSub: 'কোষাগার থেকে বিভাগে',
    kpiSpent: 'রেকর্ডকৃত ব্যয়',
    kpiSpentSub: 'অডিটকৃত প্রকৃত ব্যয়',
    kpiAvailable: 'উপলব্ধ অবশিষ্ট তহবিল',
    kpiAvailableSub: 'কোষাগারে অবশিষ্ট',
    progressTitle: 'বাজেট বাস্তবায়ন ও তহবিল প্রবাহ',
    releaseRate: 'মুক্তির হার:',
    utilisationRate: 'ব্যবহারের হার:',
    legendAllocated: 'বরাদ্দ (100%)',
    legendReleased: 'মুক্তিপ্রাপ্ত',
    legendSpent: 'ব্যয়িত',
    anomalyWarning: 'সতর্কতা: রেকর্ডকৃত ব্যয় মুক্তিপ্রাপ্ত তহবিলের চেয়ে বেশি।',
    noDataTitle: 'তথ্য উপলব্ধ নয়',
    noDataBody: 'এই নির্বাচনের জন্য বর্তমানে কোনও অফিসিয়াল আর্থিক তথ্য উপলব্ধ নেই।',
    signalsTitle: 'তহবিল সিদ্ধান্ত নির্দেশক',
    signalsSub: 'নাগরিক চাহিদা এবং আর্থিক বরাদ্দের তুলনা',
    stateComparisonTitle: 'জেলা বাজেট তুলনা',
    stateComparisonSub: 'বিস্তারিত দেখতে জেলাতে ক্লিক করুন',
    activeGrievances: 'সক্রিয় অভিযোগ',
    grievancesDonutTitle: 'খাতভিত্তিক নাগরিক অভিযোগ',
    grievancesDonutSub: 'চ্যানেলগুলোতে আসা অভিযোগের ভাগ',
    expenditureDonutTitle: 'খাতভিত্তিক ব্যয়',
    expenditureDonutSub: 'নাগরিক খাতে ব্যয়িত পাবলিক তহবিল',
    registerTitle: 'খাতভিত্তিক অগ্রাধিকার ও বাজেট রেজিস্টার',
    colSector: 'খাত',
    colGrievanceShare: 'অভিযোগের ভাগ',
    colAllocated: 'বরাদ্দ',
    colReleased: 'মুক্তিপ্রাপ্ত',
    colSpent: 'ব্যয়',
    colUtilisation: 'ব্যবহার',
    colAssessment: 'স্থিতি',
    viewGrievancesLink: 'সম্পর্কিত অভিযোগের তথ্য দেখুন →',
    methodologyTitle: 'আর্থিক ও নাগরিক চাহিদার পদ্ধতি',
    methodologyBody: 'জনসেতু সরকারি বাজেট এবং নাগরিক চাহিদাকে স্বচ্ছভাবে উপস্থাপন করে।',
  },
  gu: {
    eyebrow: 'સરકારી · નાણાકીય પારદર્શિતા',
    title: 'રાજ્ય અને જિલ્લા બજેટ',
    subtitle: 'સત્તાવાર જાહેર ભંડોળ ફાળવણી, રિલીઝ થયેલ રકમ અને ખર્ચની જનસેતુ પર નોંધાયેલ ફરિયાદો સાથે સરખામણી.',
    sourceLabel: 'સત્તાવાર સ્ત્રોત:',
    viewSource: 'સત્તાવાર સ્ત્રોત જુઓ ↗',
    publishedOn: 'પ્રકાશિત:',
    lastSynced: 'છેલ્લું સિંક:',
    verifiedBadge: 'ચકાસાયેલ ઓડિટ',
    partialBadge: 'આંશિક કવરેજ',
    scopeState: 'રાજ્ય બજેટ',
    scopeDistrict: 'જિલ્લા બજેટ',
    filterState: 'રાજ્ય',
    filterDistrict: 'જિલ્લો',
    filterYear: 'નાણાકીય વર્ષ',
    filterSector: 'નાગરિક ક્ષેત્ર',
    allSectors: 'બધા ક્ષેત્રો',
    kpiAllocated: 'કુલ ફાળવેલ બજેટ',
    kpiAllocatedSub: 'મંજૂર રાજ્ય બજેટ',
    kpiReleased: 'રિલીઝ થયેલ ભંડોળ',
    kpiReleasedSub: 'તિજોરીમાંથી વિભાગોને',
    kpiSpent: 'નોંધાયેલ ખર્ચ',
    kpiSpentSub: 'ઓડિટ થયેલ વાસ્તવિક ખર્ચ',
    kpiAvailable: 'ઉપલબ્ધ બાકી ભંડોળ',
    kpiAvailableSub: 'તિજોરીમાં બાકી',
    progressTitle: 'બજેટ અમલીકરણ અને ભંડોળ પ્રવાહ',
    releaseRate: 'રિલીઝ દર:',
    utilisationRate: 'ઉપયોગ દર:',
    legendAllocated: 'ફાળવેલ (100%)',
    legendReleased: 'રિલીઝ',
    legendSpent: 'ખર્ચ',
    anomalyWarning: 'ચેતવણી: નોંધાયેલ ખર્ચ રિલીઝ થયેલ રકમ કરતા વધારે છે.',
    noDataTitle: 'ડેટા ઉપલબ્ધ નથી',
    noDataBody: 'આ પસંદગી માટે હાલમાં કોઈ સત્તાવાર નાણાકીય માહિતી ઉપલબ્ધ નથી.',
    signalsTitle: 'નિર્ણય-સહાયક ફંડિંગ સંકેતો',
    signalsSub: 'નાગરિક માંગ અને નાણાકીય ફાળવણી વચ્ચેની સરખામણી',
    stateComparisonTitle: 'જિલ્લા બજેટ સરખામણી',
    stateComparisonSub: 'જિલ્લાવાર વિગતો માટે જિલ્લા પર ક્લિક કરો',
    activeGrievances: 'સક્રિય ફરિયાદો',
    grievancesDonutTitle: 'ક્ષેત્રવાર નાગરિક ફરિયાદો',
    grievancesDonutSub: 'નોંધાયેલ જાહેર જરૂરિયાતોનો હિસ્સો',
    expenditureDonutTitle: 'ક્ષેત્રવાર ખર્ચ',
    expenditureDonutSub: 'વિવિધ ક્ષેત્રોમાં થયેલ ખર્ચ',
    registerTitle: 'ક્ષેત્રવાર પ્રાથમિકતા અને બજેટ રજિસ્ટર',
    colSector: 'ક્ષેત્ર',
    colGrievanceShare: 'ફરિયાદ હિસ્સો',
    colAllocated: 'ફાળવણી',
    colReleased: 'રિલીઝ',
    colSpent: 'ખર્ચ',
    colUtilisation: 'ઉપયોગ',
    colAssessment: 'સ્થિતિ',
    viewGrievancesLink: 'સંબંધિત જાહેર ફરિયાદ ડેટા જુઓ →',
    methodologyTitle: 'નાણાકીય અને નાગરિક માંગ પદ્ધતિ',
    methodologyBody: 'જનસેતુ સરકારી બજેટ અને નાગરિકોની માંગનું સચોટ વિશ્લેષણ રજૂ કરે છે.',
  },
  kn: {
    eyebrow: 'ಸರ್ಕಾರ · ಆರ್ಥಿಕ ಪಾರದರ್ಶಕತೆ',
    title: 'ರಾಜ್ಯ ಮತ್ತು ಜಿಲ್ಲಾ ಬಜೆಟ್',
    subtitle: 'ಅಧಿಕೃತ ಸಾರ್ವಜನಿಕ ನಿಧಿ ಹಂಚಿಕೆ, ಬಿಡುಗಡೆ ಮತ್ತು ವೆಚ್ಚಗಳನ್ನು ಜನಸೇತು ದೂರುಗಳೊಂದಿಗೆ ಹೋಲಿಸುವುದು.',
    sourceLabel: 'ಅಧಿಕೃತ ಮೂಲ:',
    viewSource: 'ಅಧಿಕೃತ ಮೂಲವನ್ನು ವೀಕ್ಷಿಸಿ ↗',
    publishedOn: 'ಪ್ರಕಟಿಸಲಾಗಿದೆ:',
    lastSynced: 'ಕೊನೆಯ ಸಿಂಕ್:',
    verifiedBadge: 'ಪರಿಶೀಲಿಸಿದ ಆಡಿಟ್',
    partialBadge: 'ಭಾಗಶಃ ವ್ಯಾಪ್ತಿ',
    scopeState: 'ರಾಜ್ಯ ಬಜೆಟ್',
    scopeDistrict: 'ಜಿಲ್ಲಾ ಬಜೆಟ್',
    filterState: 'ರಾಜ್ಯ',
    filterDistrict: 'ಜಿಲ್ಲೆ',
    filterYear: 'ಹಣಕಾಸು ವರ್ಷ',
    filterSector: 'ಕ್ಷೇತ್ರ',
    allSectors: 'ಎಲ್ಲಾ ಕ್ಷೇತ್ರಗಳು',
    kpiAllocated: 'ಒಟ್ಟು ಹಂಚಿಕೆ',
    kpiAllocatedSub: 'ಅನುಮೋದಿತ ಬಜೆಟ್',
    kpiReleased: 'ಬಿಡುಗಡೆಯಾದ ನಿಧಿ',
    kpiReleasedSub: 'ಖಜಾನೆಯಿಂದ ಇಲಾಖೆಗಳಿಗೆ',
    kpiSpent: 'ದಾಖಲಾದ ವೆಚ್ಚ',
    kpiSpentSub: 'ಲೆಕ್ಕಪರಿಶೋಧಿತ ವೆಚ್ಚ',
    kpiAvailable: 'ಲಭ್ಯವಿರುವ ಉಳಿದ ನಿಧಿ',
    kpiAvailableSub: 'ಖಜಾನೆಯಲ್ಲಿ ಬಾಕಿ',
    progressTitle: 'ಬಜೆಟ್ ಅನುಷ್ಠಾನ ಮತ್ತು ನಿಧಿ ಹರಿವು',
    releaseRate: 'ಬಿಡುಗಡೆ ದರ:',
    utilisationRate: 'ಬಳಕೆ ದರ:',
    legendAllocated: 'ಹಂಚಿಕೆ (100%)',
    legendReleased: 'ಬಿಡುಗಡೆ',
    legendSpent: 'ವೆಚ್ಚ',
    anomalyWarning: 'ಎಚ್ಚರಿಕೆ: ದಾಖಲಾದ ವೆಚ್ಚವು ಬಿಡುಗಡೆಯಾದ ಮೊತ್ತಕ್ಕಿಂತ ಹೆಚ್ಚಾಗಿದೆ.',
    noDataTitle: 'ಡೇಟಾ ಲಭ್ಯವಿಲ್ಲ',
    noDataBody: 'ಈ ಆಯ್ಕೆಗೆ ಪ್ರಸ್ತುತ ಯಾವುದೇ ಪರಿಶೀಲಿಸಿದ ಹಣಕಾಸು ಡೇಟಾ ಲಭ್ಯವಿಲ್ಲ.',
    signalsTitle: 'ನಿರ್ಧಾರ ಬೆಂಬಲ ನಿಧಿ ಸಂಕೇತಗಳು',
    signalsSub: 'ಸಾರ್ವಜನಿಕ ಬೇಡಿಕೆ ಮತ್ತು ಹಣಕಾಸು ಹಂಚಿಕೆಯ ನಡುವಿನ ಹೋಲಿಕೆ',
    stateComparisonTitle: 'ಜಿಲ್ಲಾ ಬಜೆಟ್ ಹೋಲಿಕೆ',
    stateComparisonSub: 'ವಿವರಗಳಿಗಾಗಿ ಜಿಲ್ಲೆಯ ಮೇಲೆ ಕ್ಲಿಕ್ ಮಾಡಿ',
    activeGrievances: 'ಸಕ್ರಿಯ ದೂರುಗಳು',
    grievancesDonutTitle: 'ಕ್ಷೇತ್ರವಾರು ದೂರುಗಳು',
    grievancesDonutSub: 'ವರದಿಯಾದ ಅಗತ್ಯಗಳ ಪಾಲು',
    expenditureDonutTitle: 'ಕ್ಷೇತ್ರವಾರು ವೆಚ್ಚ',
    expenditureDonutSub: 'ಕ್ಷೇತ್ರಗಳಲ್ಲಿ ಖರ್ಚು ಮಾಡಿದ ನಿಧಿ',
    registerTitle: 'ಕ್ಷೇತ್ರ ಆದ್ಯತೆ ಮತ್ತು ಬಜೆಟ್ ರಿಜಿಸ್ಟರ್',
    colSector: 'ಕ್ಷೇತ್ರ',
    colGrievanceShare: 'ದೂರು ಪಾಲು',
    colAllocated: 'ಹಂಚಿಕೆ',
    colReleased: 'ಬಿಡುಗಡೆ',
    colSpent: 'ವೆಚ್ಚ',
    colUtilisation: 'ಬಳಕೆ',
    colAssessment: 'ಸ್ಥಿತಿ',
    viewGrievancesLink: 'ಸಾರ್ವಜನಿಕ ದೂರು ಡೇಟಾವನ್ನು ವೀಕ್ಷಿಸಿ →',
    methodologyTitle: 'ಹಣಕಾಸು ಮತ್ತು ನಾಗರಿಕ ಬೇಡಿಕೆಯ ವಿಧಾನ',
    methodologyBody: 'ಜನಸೇತು ಸರ್ಕಾರದ ಬಜೆಟ್ ಮತ್ತು ನಾಗರಿಕರ ದೂರುಗಳನ್ನು ಪಾರದರ್ಶಕವಾಗಿ ಜೋಡಿಸುತ್ತದೆ.',
  },
  ml: {
    eyebrow: 'സർക്കാർ · സാമ്പത്തിക സുതാര്യത',
    title: 'സംസ്ഥാന & ജില്ലാ ബജറ്റ്',
    subtitle: 'ഔദ്യോഗിക ഫണ്ട് വിഹിതവും ചെലവുകളും ജനസേതുവിലെ പൗരപരാതികളുമായി താരതമ്യം ചെയ്യുന്നു.',
    sourceLabel: 'ഔദ്യോഗിക ഉറവിടം:',
    viewSource: 'ഔദ്യോഗിക ഉറവിടം കാണുക ↗',
    publishedOn: 'പ്രസിദ്ധീകരിച്ചത്:',
    lastSynced: 'അവസാന സമന്വയം:',
    verifiedBadge: 'പരിശോധിച്ച ഓഡിറ്റ്',
    partialBadge: 'ഭാഗിക കവറേജ്',
    scopeState: 'സംസ്ഥാന ബജറ്റ്',
    scopeDistrict: 'ജില്ലാ ബജറ്റ്',
    filterState: 'സംസ്ഥാനം',
    filterDistrict: 'ജില്ല',
    filterYear: 'സാമ്പത്തിക വർഷം',
    filterSector: 'മേഖല',
    allSectors: 'എല്ലാ മേഖലകളും',
    kpiAllocated: 'ആകെ അനുവദിച്ചത്',
    kpiAllocatedSub: 'അംഗീകരിച്ച ബജറ്റ്',
    kpiReleased: 'അനുവദിച്ച തുക',
    kpiReleasedSub: 'വകുപ്പുകളിലേക്ക് നൽകിയത്',
    kpiSpent: 'രേഖപ്പെടുത്തിയ ചെലവ്',
    kpiSpentSub: 'ഓഡിറ്റ് ചെയ്ത തുക',
    kpiAvailable: 'ബാക്കിയുള്ള തുക',
    kpiAvailableSub: 'ട്രഷറിയിൽ ബാക്കി',
    progressTitle: 'ബജറ്റ് വിനിയോഗവും ഫണ്ട് ഒഴുക്കും',
    releaseRate: 'റിലീസ് നിരക്ക്:',
    utilisationRate: 'വിനിയോഗ നിരക്ക്:',
    legendAllocated: 'അനുവദിച്ചത് (100%)',
    legendReleased: 'റിലീസ് ചെയ്തത്',
    legendSpent: 'ചെലവഴിച്ചത്',
    anomalyWarning: 'മുന്നറിയിപ്പ്: രേഖപ്പെടുത്തിയ ചെലവ് അനുവദിച്ച തുകയേക്കാൾ കൂടുതലാണ്.',
    noDataTitle: 'ഡാറ്റ ലഭ്യമല്ല',
    noDataBody: 'ഈ തിരഞ്ഞെടുപ്പിനായി നിലവിൽ ഔദ്യോഗിക സാമ്പത്തിക വിവരങ്ങൾ ലഭ്യമല്ല.',
    signalsTitle: 'തീരുമാന സഹായ സൂചകങ്ങൾ',
    signalsSub: 'പൗരന്മാരുടെ ആവശ്യങ്ങളും ഫണ്ട് വിഹിതവും തമ്മിലുള്ള താരതമ്യം',
    stateComparisonTitle: 'ജില്ലാ ബജറ്റ് താരതമ്യം',
    stateComparisonSub: 'വിശദാംശങ്ങൾക്ക് ജില്ലയിൽ ക്ലിക്ക് ചെയ്യുക',
    activeGrievances: 'സജീവ പരാതികൾ',
    grievancesDonutTitle: 'മേഖലാടിസ്ഥാനത്തിലുള്ള പരാതികൾ',
    grievancesDonutSub: 'റിപ്പോർട്ട് ചെയ്ത ആവശ്യങ്ങളുടെ പങ്ക്',
    expenditureDonutTitle: 'മേഖലാടിസ്ഥാനത്തിലുള്ള ചെലവ്',
    expenditureDonutSub: 'വിവിധ മേഖലകളിലെ ചെലവുകൾ',
    registerTitle: 'മേഖലാ മുൻഗണനാ രജിസ്റ്റർ',
    colSector: 'മേഖല',
    colGrievanceShare: 'പരാതി വിഹിതം',
    colAllocated: 'അനുവദിച്ചത്',
    colReleased: 'റിലീസ് ചെയ്തത്',
    colSpent: 'ചെലവ്',
    colUtilisation: 'വിനിയോഗം',
    colAssessment: 'സ്ഥിതി',
    viewGrievancesLink: 'പരാതി വിവരങ്ങൾ കാണുക →',
    methodologyTitle: 'സാമ്പത്തിക & പൗര ആവശ്യ രീതിശാസ്ത്രം',
    methodologyBody: 'ജനസേതു ഔദ്യോഗിക ബജറ്റും പൗരന്മാരുടെ ആവശ്യങ്ങളും വ്യക്തമായി വിശകലനം ചെയ്യുന്നു.',
  },
  pa: {
    eyebrow: 'ਸਰਕਾਰ · ਵਿੱਤੀ ਪਾਰਦਰਸ਼ਤਾ',
    title: 'ਰਾਜ ਅਤੇ ਜ਼ਿਲ੍ਹਾ ਬਜਟ',
    subtitle: 'ਸਰਕਾਰੀ ਫੰਡ ਵੰਡ, ਜਾਰੀ ਕੀਤੇ ਫੰਡ ਅਤੇ ਖਰਚਿਆਂ ਦੀ ਜਨਸੇਤੂ ਸ਼ਿਕਾਇਤਾਂ ਨਾਲ ਸਿੱਧੀ ਤੁਲਨਾ।',
    sourceLabel: 'ਅਧਿਕਾਰਤ ਸਰੋਤ:',
    viewSource: 'ਅਧਿਕਾਰਤ ਸਰੋਤ ਦੇਖੋ ↗',
    publishedOn: 'ਪ੍ਰਕਾਸ਼ਿਤ:',
    lastSynced: 'ਆਖਰੀ ਸਿੰਕ:',
    verifiedBadge: 'ਤਸਦੀਕਸ਼ੁਦਾ ਆਡਿਟ',
    partialBadge: 'ਅੰਸ਼ਕ ਕਵਰੇਜ',
    scopeState: 'ਰਾਜ ਬਜਟ',
    scopeDistrict: 'ਜ਼ਿਲ੍ਹਾ ਬਜਟ',
    filterState: 'ਰਾਜ',
    filterDistrict: 'ਜ਼ਿਲ੍ਹਾ',
    filterYear: 'ਵਿੱਤੀ ਸਾਲ',
    filterSector: 'ਨਾਗਰਿਕ ਖੇਤਰ',
    allSectors: 'ਸਾਰੇ ਖੇਤਰ',
    kpiAllocated: 'ਕੁੱਲ ਵੰਡ',
    kpiAllocatedSub: 'ਪ੍ਰਵਾਨਿਤ ਰਾਜ ਬਜਟ',
    kpiReleased: 'ਜਾਰੀ ਫੰਡ',
    kpiReleasedSub: 'ਖਜ਼ਾਨੇ ਤੋਂ ਵਿਭਾਗਾਂ ਨੂੰ',
    kpiSpent: 'ਦਰਜ ਖਰਚਾ',
    kpiSpentSub: 'ਆਡਿਟ ਕੀਤਾ ਅਸਲ ਖਰਚਾ',
    kpiAvailable: 'ਉਪਲਬਧ ਬਾਕੀ ਫੰਡ',
    kpiAvailableSub: 'ਖਜ਼ਾਨੇ ਵਿੱਚ ਬਾਕੀ',
    progressTitle: 'ਬਜਟ ਲਾਗੂਕਰਨ ਅਤੇ ਫੰਡ ਪ੍ਰਵਾਹ',
    releaseRate: 'ਜਾਰੀ ਦਰ:',
    utilisationRate: 'ਵਰਤੋਂ ਦਰ:',
    legendAllocated: 'ਵੰਡਿਆ (100%)',
    legendReleased: 'ਜਾਰੀ',
    legendSpent: 'ਖਰਚਿਆ',
    anomalyWarning: 'ਚੇਤਾਵਨੀ: ਦਰਜ ਕੀਤਾ ਖਰਚਾ ਜਾਰੀ ਫੰਡਾਂ ਨਾਲੋਂ ਵੱਧ ਹੈ।',
    noDataTitle: 'ਡਾਟਾ ਉਪਲਬਧ ਨਹੀਂ',
    noDataBody: 'ਇਸ ਚੋਣ ਲਈ ਕੋਈ ਅਧਿਕਾਰਤ ਵਿੱਤੀ ਡਾਟਾ ਉਪਲਬਧ ਨਹੀਂ ਹੈ।',
    signalsTitle: 'ਫੰਡਿੰਗ ਸਹਾਇਤਾ ਸੰਕੇਤ',
    signalsSub: 'ਨਾਗਰਿਕ ਮੰਗ ਅਤੇ ਵਿੱਤੀ ਵੰਡ ਵਿਚਕਾਰ ਤੁਲਨਾ',
    stateComparisonTitle: 'ਜ਼ਿਲ੍ਹਾ ਬਜਟ ਤੁਲਨਾ',
    stateComparisonSub: 'ਜ਼ਿਲ੍ਹਾ ਵੇਰਵਿਆਂ ਲਈ ਜ਼ਿਲ੍ਹੇ ਤੇ ਕਲਿੱਕ ਕਰੋ',
    activeGrievances: 'ਸਰਗਰਮ ਸ਼ਿਕਾਇਤਾਂ',
    grievancesDonutTitle: 'ਖੇਤਰ ਅਨੁਸਾਰ ਸ਼ਿਕਾਇਤਾਂ',
    grievancesDonutSub: 'ਦਰਜ ਲੋੜਾਂ ਦਾ ਹਿੱਸਾ',
    expenditureDonutTitle: 'ਖੇਤਰ ਅਨੁਸਾਰ ਖਰਚਾ',
    expenditureDonutSub: 'ਖੇਤਰਾਂ ਵਿੱਚ ਖਰਚੇ ਗਏ ਫੰਡ',
    registerTitle: 'ਖੇਤਰ ਤਰਜੀਹ ਅਤੇ ਬਜਟ ਰਜਿਸਟਰ',
    colSector: 'ਖੇਤਰ',
    colGrievanceShare: 'ਸ਼ਿਕਾਇਤ ਹਿੱਸਾ',
    colAllocated: 'ਵੰਡਿਆ',
    colReleased: 'ਜਾਰੀ',
    colSpent: 'ਖਰਚਿਆ',
    colUtilisation: 'ਵਰਤੋਂ',
    colAssessment: 'ਸਥਿਤੀ',
    viewGrievancesLink: 'ਸੰਬੰਧਿਤ ਸ਼ਿਕਾਇਤ ਡਾਟਾ ਦੇਖੋ →',
    methodologyTitle: 'ਵਿੱਤੀ ਅਤੇ ਨਾਗਰਿਕ ਮੰਗ ਵਿਧੀ',
    methodologyBody: 'ਜਨਸੇਤੂ ਸਰਕਾਰੀ ਬਜਟ ਅਤੇ ਨਾਗਰਿਕ ਸ਼ਿਕਾਇਤਾਂ ਨੂੰ ਪਾਰਦਰਸ਼ੀ ਤਰੀਕੇ ਨਾਲ ਪੇਸ਼ ਕਰਦਾ ਹੈ।',
  },
  or: {
    eyebrow: 'ସରକାର · ଆର୍ଥିକ ସ୍ୱଚ୍ଛତା',
    title: 'ରାଜ୍ୟ ଓ ଜିଲ୍ଲା ବଜେଟ୍',
    subtitle: 'ସରକାରୀ ପାଣ୍ଠି ବଣ୍ଟନ, ମୁକ୍ତ ରାଶି ଏବଂ ଖର୍ଚ୍ଚର ଜନସେତୁ ଅଭିଯୋଗ ସହିତ ସିଧାସଳଖ ତୁଳନା।',
    sourceLabel: 'ସରକାରୀ ଉତ୍ସ:',
    viewSource: 'ସରକାରୀ ଉତ୍ସ ଦେଖନ୍ତୁ ↗',
    publishedOn: 'ପ୍ରକାଶିତ:',
    lastSynced: 'ଶେଷ ସିଙ୍କ୍:',
    verifiedBadge: 'ଯାଞ୍ଚ ହୋଇଥିବା ଅଡିଟ୍',
    partialBadge: 'ଆଂଶିକ କଭରେଜ୍',
    scopeState: 'ରାଜ୍ୟ ବଜେଟ୍',
    scopeDistrict: 'ଜିଲ୍ଲା ବଜେଟ୍',
    filterState: 'ରାଜ୍ୟ',
    filterDistrict: 'ଜିଲ୍ଲା',
    filterYear: 'ଆର୍ଥିକ ବର୍ଷ',
    filterSector: 'ନାଗରିକ କ୍ଷେତ୍ର',
    allSectors: 'ସମସ୍ତ କ୍ଷେତ୍ର',
    kpiAllocated: 'ମୋଟ ଆବଣ୍ଟିତ',
    kpiAllocatedSub: 'ଅନୁମୋଦିତ ବଜେଟ୍',
    kpiReleased: 'ମୁକ୍ତ ପାଣ୍ଠି',
    kpiReleasedSub: 'କୋଷାଗାରରୁ ବିଭାଗକୁ',
    kpiSpent: 'ରେକର୍ଡ ହୋଇଥିବା ଖର୍ଚ୍ଚ',
    kpiSpentSub: 'ଅଡିଟ୍ ହୋଇଥିବା ଖର୍ଚ୍ଚ',
    kpiAvailable: 'ଉପଲବ୍ଧ ବଳକା ପାଣ୍ଠି',
    kpiAvailableSub: 'କୋଷାଗାରରେ ବଳକା',
    progressTitle: 'ବଜେଟ୍ କାର୍ଯ୍ୟାନ୍ୱୟନ ଏବଂ ପାଣ୍ଠି ପ୍ରବାହ',
    releaseRate: 'ମୁକ୍ତି ହାର:',
    utilisationRate: 'ବ୍ୟବହାର ହାର:',
    legendAllocated: 'ଆବଣ୍ଟିତ (100%)',
    legendReleased: 'ମୁକ୍ତ',
    legendSpent: 'ଖର୍ଚ୍ଚ',
    anomalyWarning: 'ଚେତାବନୀ: ରେକର୍ଡ ହୋଇଥିବା ଖର୍ଚ୍ଚ ମୁକ୍ତ ପାଣ୍ଠିଠାରୁ ଅଧିକ।',
    noDataTitle: 'ତଥ୍ୟ ଉପଲବ୍ଧ ନାହିଁ',
    noDataBody: 'ଏହି ଚୟନ ପାଇଁ କୌଣସି ସରକାରୀ ଆର୍ଥିକ ତଥ୍ୟ ଉପଲବ୍ଧ ନାହିଁ।',
    signalsTitle: 'ନିଷ୍ପତ୍ତି ସହାୟତା ପାଣ୍ଠି ସଙ୍କେତ',
    signalsSub: 'ନାଗରିକ ଚାହିଦା ଏବଂ ପାଣ୍ଠି ବଣ୍ଟନ ମଧ୍ୟରେ ତୁଳନା',
    stateComparisonTitle: 'ଜିଲ୍ଲା ବଜେଟ୍ ତୁଳନା',
    stateComparisonSub: 'ବିବରଣୀ ପାଇଁ ଜିଲ୍ଲା ଉପରେ କ୍ଲିକ୍ କରନ୍ତୁ',
    activeGrievances: 'ସକ୍ରିୟ ଅଭିଯୋଗ',
    grievancesDonutTitle: 'କ୍ଷେତ୍ର ଅନୁଯାୟୀ ଅଭିଯୋଗ',
    grievancesDonutSub: 'ଦାଖଲ ହୋଇଥିବା ଆବଶ୍ୟକତାର ଅଂଶ',
    expenditureDonutTitle: 'କ୍ଷେତ୍ର ଅନୁଯାୟୀ ଖର୍ଚ୍ଚ',
    expenditureDonutSub: 'ବିଭିନ୍ନ କ୍ଷେତ୍ରରେ ଖର୍ଚ୍ଚ ହୋଇଥିବା ପାଣ୍ଠି',
    registerTitle: 'କ୍ଷେତ୍ର ପ୍ରାଥମିକତା ଓ ବଜେଟ୍ ରେଜିଷ୍ଟର',
    colSector: 'କ୍ଷେତ୍ର',
    colGrievanceShare: 'ଅଭିଯୋଗ ଅଂଶ',
    colAllocated: 'ଆବଣ୍ଟନ',
    colReleased: 'ମୁକ୍ତ',
    colSpent: 'ଖର୍ଚ୍ଚ',
    colUtilisation: 'ବ୍ୟବହାର',
    colAssessment: 'ସ୍ଥିତି',
    viewGrievancesLink: 'ଅଭିଯୋଗ ତଥ୍ୟ ଦେଖନ୍ତୁ →',
    methodologyTitle: 'ଆର୍ଥିକ ଏବଂ ନାଗରିକ ଚାହିଦା ପଦ୍ଧତି',
    methodologyBody: 'ଜନସେତୁ ସରକାରୀ ବଜେଟ୍ ଏବଂ ନାଗରିକ ଅଭିଯୋଗକୁ ସ୍ୱଚ୍ଛ ଭାବରେ ଉପସ୍ଥାପନ କରେ।',
  },
  as: {
    eyebrow: 'চৰকাৰী · বিত্তীয় স্বচ্ছতা',
    title: 'ৰাজ্যিক আৰু জিলা বাজেট',
    subtitle: 'চৰকাৰী পুঁজি আৱণ্টন, মুকলি আৰু খৰচৰ জনসেতুৰ অভিযোগৰ সৈতে পোনপটীয়া তুলনা।',
    sourceLabel: 'চৰকাৰী উৎস:',
    viewSource: 'চৰকাৰী উৎস চাওক ↗',
    publishedOn: 'প্ৰকাশিত:',
    lastSynced: 'অন্তিম সমন্বয়:',
    verifiedBadge: 'পৰীক্ষিত অডিট',
    partialBadge: 'আংশিক কভাৰেজ',
    scopeState: 'ৰাজ্যিক বাজেট',
    scopeDistrict: 'জিলা বাজেট',
    filterState: 'ৰাজ্য',
    filterDistrict: 'জিলা',
    filterYear: 'বিত্তীয় বৰ্ষ',
    filterSector: 'নাগৰিক খণ্ড',
    allSectors: 'সকলো খণ্ড',
    kpiAllocated: 'মুঠ আৱণ্টন',
    kpiAllocatedSub: 'অনুমোদিত ৰাজ্যিক বাজেট',
    kpiReleased: 'মুকলি পুঁজি',
    kpiReleasedSub: 'কোষাগাৰৰ পৰা বিভাগলৈ',
    kpiSpent: 'নথিভুক্ত খৰচ',
    kpiSpentSub: 'পৰীক্ষিত প্ৰকৃত খৰচ',
    kpiAvailable: 'উপলব্ধ বাকী পুঁজি',
    kpiAvailableSub: 'কোষাগাৰত বাকী',
    progressTitle: 'বাজেট ৰূপায়ণ আৰু পুঁজি প্ৰবাহ',
    releaseRate: 'মুকলিৰ হাৰ:',
    utilisationRate: 'ব্যৱহাৰৰ হাৰ:',
    legendAllocated: 'আৱণ্টন (100%)',
    legendReleased: 'মুকলি',
    legendSpent: 'খৰচ',
    anomalyWarning: 'সতৰ্কবাণী: নথিভুক্ত খৰচ মুকলি পুঁজিতকৈ অধিক।',
    noDataTitle: 'তথ্য উপলব্ধ নহয়',
    noDataBody: 'এই নিৰ্বাচনৰ বাবে কোনো চৰকাৰী বিত্তীয় তথ্য উপলব্ধ নহয়।',
    signalsTitle: 'সিদ্ধান্ত সমৰ্থন পুঁজি সংকেত',
    signalsSub: 'নাগৰিক চাহিদা আৰু পুঁজি আৱণ্টনৰ তুলনা',
    stateComparisonTitle: 'জিলা বাজেট তুলনা',
    stateComparisonSub: 'বিৱৰণ চাবলৈ জিলাত ক্লিক কৰক',
    activeGrievances: 'সক্ৰিয় অভিযোগ',
    grievancesDonutTitle: 'খণ্ডভিত্তিক অভিযোগ',
    grievancesDonutSub: 'দাখিল কৰা প্ৰয়োজনৰ অংশ',
    expenditureDonutTitle: 'খণ্ডভিত্তিক খৰচ',
    expenditureDonutSub: 'খণ্ডসমূহত হোৱা খৰচ',
    registerTitle: 'খণ্ড প্ৰাথমিকতা আৰু বাজেট পঞ্জী',
    colSector: 'খণ্ড',
    colGrievanceShare: 'অভিযোগৰ অংশ',
    colAllocated: 'আৱণ্টন',
    colReleased: 'মুকলি',
    colSpent: 'খৰচ',
    colUtilisation: 'ব্যৱহাৰ',
    colAssessment: 'স্থিতি',
    viewGrievancesLink: 'অভিযোগ তথ্য চাওক →',
    methodologyTitle: 'বিত্তীয় আৰু নাগৰিক চাহিদা পদ্ধতি',
    methodologyBody: 'জনসেতুৱে চৰকাৰী বাজেট আৰু নাগৰিকৰ চাহিদাক স্বচ্ছভাৱে উপস্থাপন কৰে।',
  },
  ur: {
    eyebrow: 'حکومتی · مالیاتی شفافیت',
    title: 'ریاستی اور ضلعی بجٹ',
    subtitle: 'سرکاری فنڈز کی الاٹمنٹ، جاری کردہ رقوم اور اخراجات کا جن سیتو کی عوامی شکایات سے براہ راست موازنہ۔',
    sourceLabel: 'سرکاری ذریعہ:',
    viewSource: 'سرکاری ذریعہ دیکھیں ↗',
    publishedOn: 'شائع کردہ:',
    lastSynced: 'آخری ہم آہنگی:',
    verifiedBadge: 'تصدیق شدہ سرکاری آڈٹ',
    partialBadge: 'جزوی کوریج',
    scopeState: 'ریاستی بجٹ',
    scopeDistrict: 'ضلعی بجٹ',
    filterState: 'ریاست',
    filterDistrict: 'ضلع',
    filterYear: 'مالی سال',
    filterSector: 'شہری شعبہ',
    allSectors: 'تمام شعبے',
    kpiAllocated: 'کل الاٹمنٹ',
    kpiAllocatedSub: 'منظور شدہ ریاستی بجٹ',
    kpiReleased: 'جاری کردہ فنڈز',
    kpiReleasedSub: 'خزانے سے محکموں کو',
    kpiSpent: 'ریکارڈ شدہ اخراجات',
    kpiSpentSub: 'آڈٹ شدہ اصل اخراجات',
    kpiAvailable: 'دستیاب بقیہ فنڈز',
    kpiAvailableSub: 'خزانے میں باقی',
    progressTitle: 'بجٹ کا نفاذ اور فنڈز کا بہاؤ',
    releaseRate: 'جاری کرنے کی شرح:',
    utilisationRate: 'استعمال کی شرح:',
    legendAllocated: 'الاٹ شدہ (100%)',
    legendReleased: 'جاری شدہ',
    legendSpent: 'خرچ شدہ',
    anomalyWarning: 'انتباہ: ریکارڈ شدہ اخراجات جاری کردہ فنڈز سے زیادہ ہیں۔',
    noDataTitle: 'ڈیٹا دستیاب نہیں ہے',
    noDataBody: 'اس انتخاب کے لیے فی الحال کوئی سرکاری مالیاتی ڈیٹا دستیاب نہیں ہے۔',
    signalsTitle: 'فیصلہ ساز فنڈنگ اشارے',
    signalsSub: 'عوامی مطالبات اور مالیاتی الاٹمنٹ کا موازنہ',
    stateComparisonTitle: 'ضلعی بجٹ کا موازنہ',
    stateComparisonSub: 'تفصیلات کے لیے ضلع پر کلک کریں',
    activeGrievances: 'فعال شکایات',
    grievancesDonutTitle: 'شعبہ وار شکایات',
    grievancesDonutSub: 'عوامی ضروریات کا تناسب',
    expenditureDonutTitle: 'شعبہ وار اخراجات',
    expenditureDonutSub: 'مختلف شعبوں میں خرچ کردہ فنڈز',
    registerTitle: 'شعبہ جاتی ترجیحات اور بجٹ رجسٹر',
    colSector: 'شعبہ',
    colGrievanceShare: 'شکایات کا حصہ',
    colAllocated: 'الاٹمنٹ',
    colReleased: 'جاری شدہ',
    colSpent: 'اخراجات',
    colUtilisation: 'استعمال',
    colAssessment: 'حیثیت',
    viewGrievancesLink: 'عوامی شکایات کا ڈیٹا دیکھیں →',
    methodologyTitle: 'مالیاتی اور عوامی ڈیمانڈ طریقہ کار',
    methodologyBody: 'جن سیتو سرکاری بجٹ اور عوامی شکایات کو شفاف انداز میں پیش کرتا ہے۔',
  },
}

const SUPPORTED_LANG_OPTIONS = [
  { code: 'en', name: 'English', native: 'English' },
  { code: 'hi', name: 'Hindi', native: 'हिन्दी' },
  { code: 'mr', name: 'Marathi', native: 'मराठी' },
  { code: 'ta', name: 'Tamil', native: 'தமிழ்' },
  { code: 'te', name: 'Telugu', native: 'తెలుగు' },
  { code: 'bn', name: 'Bengali', native: 'বাংলা' },
  { code: 'gu', name: 'Gujarati', native: 'ગુજરાતી' },
  { code: 'kn', name: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'ml', name: 'Malayalam', native: 'മലയാളം' },
  { code: 'pa', name: 'Punjabi', native: 'ਪੰਜਾਬੀ' },
  { code: 'or', name: 'Odia', native: 'ଓଡ଼ିଆ' },
  { code: 'as', name: 'Assamese', native: 'অসমীয়া' },
  { code: 'ur', name: 'Urdu', native: 'اردو' },
]

export default function PublicFunds() {
  const caps = useCapabilities()
  const [pageLang, setPageLang] = useState('en') // Default language is English
  const t = I18N[pageLang] || I18N.en

  const [searchParams, setSearchParams] = useSearchParams()

  // Read URL parameters with reliable defaults
  const scope = searchParams.get('scope') || 'state'
  const selectedState = searchParams.get('state') || 'Maharashtra'
  const selectedDistrict = searchParams.get('district') || ''
  const selectedYear = searchParams.get('year') || '2026-27'
  const selectedCategory = searchParams.get('sector') || 'ALL'

  const [statesList, setStatesList] = useState(['Maharashtra', 'Tamil Nadu'])
  const [districtsList, setDistrictsList] = useState([])
  const [coverage, setCoverage] = useState({
    covered_states: [],
    covered_districts: [],
    covered_district_codes: [],
  })

  const [overview, setOverview] = useState(null)
  const [districtsData, setDistrictsData] = useState([])
  const [sectorsData, setSectorsData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Load verified coverage and covered states
  useEffect(() => {
    getStates()
      .then((res) => {
        if (res && res.length > 0) {
          setStatesList(res)
        }
      })
      .catch(() => {})

    getFundsCoverage()
      .then((cov) => {
        if (cov) {
          setCoverage(cov)
        }
      })
      .catch(() => {})
  }, [])

  // Load districts for selected state
  useEffect(() => {
    if (selectedState) {
      getDistricts({ state: selectedState })
        .then((res) => {
          const list = res || []
          setDistrictsList(list)
          if (scope === 'district' && list.length > 0) {
            const hasMatch = list.some((d) => d.name === selectedDistrict || d.code === selectedDistrict)
            if (!hasMatch) {
              updateParams({ district: list[0].name })
            }
          }
        })
        .catch(() => setDistrictsList([]))
    }
  }, [selectedState, scope])

  // Fetch Public Funds data
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const effectiveDistrict =
      scope === 'district'
        ? selectedDistrict || districtsList[0]?.name || undefined
        : undefined

    const pOverview = getFundsOverview({
      scope,
      state: selectedState,
      district: effectiveDistrict,
      fiscalYear: selectedYear,
      category: selectedCategory !== 'ALL' ? selectedCategory : undefined,
    })

    const pDistricts =
      scope === 'state'
        ? getFundsDistricts({
            state: selectedState,
            fiscalYear: selectedYear,
            category: selectedCategory !== 'ALL' ? selectedCategory : undefined,
          })
        : Promise.resolve([])

    const pSectors = getFundsSectors({
      scope,
      state: selectedState,
      district: effectiveDistrict,
      fiscalYear: selectedYear,
    })

    Promise.all([pOverview, pDistricts, pSectors])
      .then(([ov, dists, secs]) => {
        if (!cancelled) {
          setOverview(ov)
          setDistrictsData(dists || [])
          setSectorsData(secs || [])
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message || 'Failed to load public funds data')
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [scope, selectedState, selectedDistrict, selectedYear, selectedCategory, districtsList])

  // Update query params helper
  function updateParams(newParams) {
    const updated = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(newParams)) {
      if (v === null || v === undefined || v === '') {
        updated.delete(k)
      } else {
        updated.set(k, v)
      }
    }
    setSearchParams(updated)
  }

  // Derive decision support signals
  const fundingSignals = useMemo(() => {
    if (!sectorsData || sectorsData.length === 0) return []
    const signals = []

    for (const s of sectorsData) {
      if (s.need_gap > 8.0) {
        signals.push({
          type: 'warn',
          text: `${s.label} appears under-weighted: citizen grievance share is ${s.grievance_share_pct}%, but received only ${s.allocation_share_pct}% of budget allocation.`,
        })
      } else if (s.need_gap < -6.0) {
        signals.push({
          type: 'attention',
          text: `${s.label} allocation (${s.allocation_share_pct}%) is moving faster than citizen grievance volume (${s.grievance_share_pct}%).`,
        })
      } else if (s.allocated > 0 && Math.abs(s.need_gap) <= 5.0) {
        signals.push({
          type: 'aligned',
          text: `${s.label} budget allocation (${s.allocation_share_pct}%) and citizen demand (${s.grievance_share_pct}%) are broadly aligned.`,
        })
      }
    }

    if (signals.length === 0) {
      signals.push({
        type: 'aligned',
        text: 'All civic sectors have balanced allocations against recorded citizen grievances.',
      })
    }
    return signals
  }, [sectorsData])

  // Donut chart datasets
  const grievanceDonutData = useMemo(() => {
    return sectorsData
      .filter((s) => s.active_grievances > 0)
      .map((s) => ({
        name: s.label,
        value: s.active_grievances,
        color: s.color,
      }))
  }, [sectorsData])

  const expenditureDonutData = useMemo(() => {
    return sectorsData
      .filter((s) => s.spent > 0)
      .map((s) => ({
        name: s.label,
        value: s.spent,
        color: s.color,
      }))
  }, [sectorsData])

  const totalGrievances = overview?.total_active_grievances || 0
  const totalSpent = overview?.recorded_expenditure || 0

  return (
    <div className="funds-container">
      {/* Header & Language Selection */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div className="funds-header" style={{ flex: 1, minWidth: '280px' }}>
          <div className="funds-eyebrow">{t.eyebrow}</div>
          <h1 className="funds-title">{t.title}</h1>
          <p className="page-head__sub" style={{ margin: 0 }}>
            {t.subtitle}
          </p>

          {overview?.metadata ? (
            <div className="funds-provenance">
              <span>
                <strong>{t.sourceLabel}</strong> {overview.metadata.source_name}
              </span>
              <a
                href={overview.metadata.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t.viewSource}
              </a>
              {overview.metadata.published_at ? (
                <span>
                  {t.publishedOn}{' '}
                  {new Date(overview.metadata.published_at).toLocaleDateString()}
                </span>
              ) : null}
              {overview.coverage === 'complete' ? (
                <span className="badge--verified">✓ {t.verifiedBadge}</span>
              ) : (
                <span className="badge--partial">⚠ {t.partialBadge}</span>
              )}
            </div>
          ) : null}
        </div>

        {/* Prominent Language Dropdown Selector */}
        <div
          className="funds-lang-selector"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: '#ffffff',
            padding: '8px 14px',
            borderRadius: '10px',
            border: '1px solid var(--rule, #e2e8f0)',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)',
          }}
        >
          <span style={{ fontSize: '16px' }}>🌐</span>
          <label style={{ fontSize: '13px', fontWeight: 700, color: 'var(--ink-2, #475569)' }}>
            Language:
          </label>
          <select
            className="funds-select"
            value={pageLang}
            onChange={(e) => setPageLang(e.target.value)}
            style={{ fontWeight: 600, padding: '5px 10px' }}
          >
            {SUPPORTED_LANG_OPTIONS.map((l) => (
              <option key={l.code} value={l.code}>
                {l.native} — {l.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="funds-filter-bar">
        {/* Scope Toggle */}
        <div className="funds-scope-switch" role="tablist" aria-label="Budget Scope">
          <button
            type="button"
            className={`funds-scope-btn${scope === 'state' ? ' funds-scope-btn--active' : ''}`}
            onClick={() => updateParams({ scope: 'state', district: '' })}
          >
            {t.scopeState}
          </button>
          <button
            type="button"
            className={`funds-scope-btn${scope === 'district' ? ' funds-scope-btn--active' : ''}`}
            onClick={() => {
              const defaultDist = districtsList[0]?.name || 'Pune'
              updateParams({ scope: 'district', district: selectedDistrict || defaultDist })
            }}
          >
            {t.scopeDistrict}
          </button>
        </div>

        {/* Dropdown Filters */}
        <div className="funds-select-group">
          <label className="funds-field">
            {t.filterState}:
            <select
              className="funds-select"
              value={selectedState}
              onChange={(e) => updateParams({ state: e.target.value, district: '' })}
            >
              {statesList.map((st) => {
                const isCovered =
                  coverage.covered_states.length > 0 &&
                  coverage.covered_states.includes(st)
                return (
                  <option key={st} value={st}>
                    {isCovered ? `🟢 ${st}` : `🔴 ${st}`}
                  </option>
                )
              })}
            </select>
          </label>

          {scope === 'district' ? (
            <label className="funds-field">
              {t.filterDistrict}:
              <select
                className="funds-select"
                value={selectedDistrict}
                onChange={(e) => updateParams({ district: e.target.value })}
              >
                {districtsList.map((d) => {
                  const isCovered =
                    coverage.covered_districts.includes(d.name) ||
                    coverage.covered_district_codes.includes(d.code)
                  return (
                    <option key={d.code} value={d.name}>
                      {isCovered ? `🟢 ${d.name}` : `🔴 ${d.name}`}
                    </option>
                  )
                })}
              </select>
            </label>
          ) : null}

          <label className="funds-field">
            {t.filterYear}:
            <select
              className="funds-select"
              value={selectedYear}
              onChange={(e) => updateParams({ year: e.target.value })}
            >
              <option value="2026-27">2026–27 (Current)</option>
              <option value="2025-26">2025–26</option>
            </select>
          </label>

          <label className="funds-field">
            {t.filterSector}:
            <select
              className="funds-select"
              value={selectedCategory}
              onChange={(e) => updateParams({ sector: e.target.value })}
            >
              <option value="ALL">{t.allSectors}</option>
              {caps.data?.categories?.map((cat) => (
                <option key={cat.code} value={cat.code}>
                  {cat.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {loading ? (
        <Loading label="Reconciling official state budget publications & citizen demand..." />
      ) : error ? (
        <ErrorState error={error} title="Failed to load public funds" />
      ) : !overview?.is_data_available && overview?.total_allocated === 0 ? (
        <div className="funds-card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <h2 className="funds-card__title" style={{ fontSize: '20px' }}>
            {t.noDataTitle}
          </h2>
          <p className="funds-card__sub" style={{ maxWidth: '600px', margin: '8px auto 0' }}>
            {t.noDataBody}
          </p>
        </div>
      ) : (
        <>
          {/* Anomaly Banner if spent > released */}
          {overview?.has_anomaly ? (
            <div className="funds-anomaly-banner">
              <span>⚠️</span>
              <span>{t.anomalyWarning}</span>
            </div>
          ) : null}

          {/* 4 Connected Summary KPI Cards */}
          <div className="funds-kpi-grid">
            <div className="funds-kpi-card funds-kpi-card--alloc">
              <span className="funds-kpi-label">{t.kpiAllocated}</span>
              <span className="funds-kpi-value">₹{overview.total_allocated.toLocaleString()} Cr</span>
              <span className="funds-kpi-sub">{t.kpiAllocatedSub}</span>
            </div>

            <div className="funds-kpi-card funds-kpi-card--rel">
              <span className="funds-kpi-label">{t.kpiReleased}</span>
              <span className="funds-kpi-value">₹{overview.funds_released.toLocaleString()} Cr</span>
              <span className="funds-kpi-sub">
                {overview.release_rate_pct}% {t.releaseRate}
              </span>
            </div>

            <div className="funds-kpi-card funds-kpi-card--spent">
              <span className="funds-kpi-label">{t.kpiSpent}</span>
              <span className="funds-kpi-value">₹{overview.recorded_expenditure.toLocaleString()} Cr</span>
              <span className="funds-kpi-sub">
                {overview.utilisation_rate_pct}% {t.utilisationRate}
              </span>
            </div>

            <div className="funds-kpi-card funds-kpi-card--avail">
              <span className="funds-kpi-label">{t.kpiAvailable}</span>
              <span
                className="funds-kpi-value"
                style={{ color: overview.available_funds < 0 ? '#dc2626' : undefined }}
              >
                ₹{overview.available_funds.toLocaleString()} Cr
              </span>
              <span className="funds-kpi-sub">{t.kpiAvailableSub}</span>
            </div>
          </div>

          {/* Proportional Progress Bar */}
          <div className="funds-progress-card">
            <div className="funds-progress-head">
              <span>{t.progressTitle}</span>
              <div className="funds-progress-rates">
                <span>
                  {t.releaseRate} <strong>{overview.release_rate_pct}%</strong>
                </span>
                <span>
                  {t.utilisationRate} <strong>{overview.utilisation_rate_pct}%</strong>
                </span>
              </div>
            </div>

            <div className="funds-progress-bar-track">
              <div
                className="funds-progress-fill--rel"
                style={{ width: `${Math.min(overview.release_rate_pct, 100)}%` }}
              />
              <div
                className="funds-progress-fill--spent"
                style={{
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  width: `${Math.min((overview.recorded_expenditure / (overview.total_allocated || 1)) * 100, 100)}%`,
                }}
              />
            </div>

            <div className="funds-legend">
              <div className="funds-legend-item">
                <span className="funds-legend-swatch" style={{ background: '#e2e8f0' }} />
                <span>{t.legendAllocated}</span>
              </div>
              <div className="funds-legend-item">
                <span className="funds-legend-swatch" style={{ background: '#93c5fd' }} />
                <span>{t.legendReleased}</span>
              </div>
              <div className="funds-legend-item">
                <span className="funds-legend-swatch" style={{ background: '#10b981' }} />
                <span>{t.legendSpent}</span>
              </div>
            </div>
          </div>

          {/* 2-Column Section: State Comparison (or District Detail) + Decision Signals */}
          <div className="funds-grid-2col">
            {scope === 'state' ? (
              <div className="funds-card">
                <div>
                  <h2 className="funds-card__title">{t.stateComparisonTitle}</h2>
                  <p className="funds-card__sub">{t.stateComparisonSub}</p>
                </div>

                <div className="district-bars-list">
                  {districtsData.slice(0, 8).map((d) => (
                    <div
                      key={d.district_code}
                      className="district-bar-row"
                      onClick={() => updateParams({ scope: 'district', district: d.district })}
                      title={`Click to view ${d.district} district budget`}
                    >
                      <div className="district-bar-meta">
                        <span>{d.district}</span>
                        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                          <span className="district-bar-grievances">
                            {d.active_grievances} {t.activeGrievances}
                          </span>
                          <strong>₹{d.allocated} Cr</strong>
                        </div>
                      </div>
                      <div className="district-bar-track">
                        <div
                          className="district-bar-fill"
                          style={{
                            width: `${Math.min((d.allocated / (overview.total_allocated || 1)) * 100, 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="funds-card">
                <div>
                  <h2 className="funds-card__title">
                    {selectedDistrict} District Budget Profile
                  </h2>
                  <p className="funds-card__sub">
                    Authorized allocations and active grievances for {selectedDistrict},{' '}
                    {selectedState}
                  </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' }}>
                    <span style={{ color: '#64748b' }}>Active Citizen Grievances:</span>
                    <strong>{overview.total_active_grievances} reports</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' }}>
                    <span style={{ color: '#64748b' }}>Budget Allocated:</span>
                    <strong>₹{overview.total_allocated} Cr</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' }}>
                    <span style={{ color: '#64748b' }}>Funds Released:</span>
                    <strong>₹{overview.funds_released} Cr</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' }}>
                    <span style={{ color: '#64748b' }}>Recorded Expenditure:</span>
                    <strong>₹{overview.recorded_expenditure} Cr</strong>
                  </div>
                </div>
              </div>
            )}

            {/* Decision Support Signals */}
            <div className="funds-card">
              <div>
                <h2 className="funds-card__title">{t.signalsTitle}</h2>
                <p className="funds-card__sub">{t.signalsSub}</p>
              </div>

              <div className="signals-list">
                {fundingSignals.map((sig, idx) => (
                  <div key={idx} className={`signal-item signal-item--${sig.type}`}>
                    <span>
                      {sig.type === 'warn' ? '⚠️' : sig.type === 'attention' ? 'ℹ️' : '✓'}
                    </span>
                    <span>{sig.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 2 Donut Charts: Citizen Grievances vs Expenditure */}
          <div className="funds-grid-2col">
            {/* The Need: Citizen Grievances by Sector */}
            <div className="funds-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #f1f5f9', paddingBottom: '12px' }}>
                <div>
                  <p className="eyebrow" style={{ color: '#64748b', fontSize: '10.5px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', margin: '0 0 2px' }}>
                    THE NEED
                  </p>
                  <h2 className="funds-card__title" style={{ margin: 0 }}>{t.grievancesDonutTitle}</h2>
                </div>
                <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 500 }}>
                  {t.grievancesDonutSub}
                </span>
              </div>

              <div className="funds-donut-layout">
                <div className="funds-donut-chart-box">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={grievanceDonutData}
                        innerRadius={52}
                        outerRadius={78}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {grievanceDonutData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(val, name) => [`${val} grievances`, name]}
                        contentStyle={{ background: '#0f172a', color: '#fff', borderRadius: '8px', border: 0, fontSize: '12px' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="funds-donut-center">
                    <strong>{totalGrievances.toLocaleString()}</strong>
                    <small>active cases</small>
                  </div>
                </div>

                <div className="funds-donut-legend">
                  {sectorsData.map((s) => (
                    <div key={s.category} className="funds-donut-legend-row">
                      <span className="funds-donut-legend-label">
                        <span className="funds-donut-legend-swatch" style={{ background: s.color }} />
                        {s.label}
                      </span>
                      <span className="funds-donut-legend-val">{s.grievance_share_pct}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* The Spending: Expenditure by Sector */}
            <div className="funds-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #f1f5f9', paddingBottom: '12px' }}>
                <div>
                  <p className="eyebrow" style={{ color: '#64748b', fontSize: '10.5px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', margin: '0 0 2px' }}>
                    THE SPENDING
                  </p>
                  <h2 className="funds-card__title" style={{ margin: 0 }}>{t.expenditureDonutTitle}</h2>
                </div>
                <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 500 }}>
                  Share of ₹{overview.recorded_expenditure.toLocaleString()} Cr spent
                </span>
              </div>

              <div className="funds-donut-layout">
                <div className="funds-donut-chart-box">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={expenditureDonutData}
                        innerRadius={52}
                        outerRadius={78}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {expenditureDonutData.map((entry, index) => (
                          <Cell key={`cell-exp-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(val, name) => [`₹${val} Cr`, name]}
                        contentStyle={{ background: '#0f172a', color: '#fff', borderRadius: '8px', border: 0, fontSize: '12px' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="funds-donut-center">
                    <strong>₹{overview.recorded_expenditure.toLocaleString()}</strong>
                    <small>crore spent</small>
                  </div>
                </div>

                <div className="funds-donut-legend">
                  {sectorsData.map((s) => {
                    const spendShare = overview.recorded_expenditure > 0
                      ? Math.round((s.spent / overview.recorded_expenditure) * 100)
                      : 0
                    return (
                      <div key={s.category} className="funds-donut-legend-row">
                        <span className="funds-donut-legend-label">
                          <span className="funds-donut-legend-swatch" style={{ background: s.color }} />
                          {s.label}
                        </span>
                        <span className="funds-donut-legend-val">{spendShare}%</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Sector Priority Register Table */}
          <div className="funds-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h2 className="funds-card__title">{t.registerTitle}</h2>
                <p className="funds-card__sub">
                  Detailed sector-wise audit and public demand reconciliation
                </p>
              </div>
              <Link
                to={`/dashboard?state=${encodeURIComponent(selectedState)}`}
                className="funds-table-link"
              >
                {t.viewGrievancesLink}
              </Link>
            </div>

            <div className="funds-table-wrap">
              <table className="funds-table">
                <thead>
                  <tr>
                    <th>{t.colSector}</th>
                    <th>{t.colGrievanceShare}</th>
                    <th>{t.colAllocated}</th>
                    <th>{t.colReleased}</th>
                    <th>{t.colSpent}</th>
                    <th>{t.colUtilisation}</th>
                    <th>{t.colAssessment}</th>
                  </tr>
                </thead>
                <tbody>
                  {sectorsData.map((s) => (
                    <tr key={s.category}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span
                            style={{
                              width: '10px',
                              height: '10px',
                              borderRadius: '50%',
                              background: s.color,
                              display: 'inline-block',
                            }}
                          />
                          <strong>{s.label}</strong>
                        </div>
                      </td>
                      <td>
                        {s.grievance_share_pct}% ({s.active_grievances})
                      </td>
                      <td>₹{s.allocated} Cr</td>
                      <td>₹{s.released} Cr</td>
                      <td>₹{s.spent} Cr</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div style={{ width: '60px', height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                            <div
                              style={{
                                width: `${Math.min(s.utilisation_rate, 100)}%`,
                                height: '100%',
                                background: '#10b981',
                              }}
                            />
                          </div>
                          <span style={{ fontSize: '12px' }}>{s.utilisation_rate}%</span>
                        </div>
                      </td>
                      <td>
                        <span className={`badge-tag badge-tag--${s.assessment_type}`}>
                          {s.assessment}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Methodology Notice */}
          <div className="funds-methodology">
            <strong>ℹ️ {t.methodologyTitle}: </strong>
            {t.methodologyBody}
          </div>
        </>
      )}
    </div>
  )
}
