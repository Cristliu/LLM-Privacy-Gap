<style>
  .latex-table-block {
    width: 100%;
    margin: 0 auto;
    color: #000;
    font-family: "Times New Roman", Times, serif;
  }

  .latex-table-title {
    margin: 0 0 34px;
    text-align: center;
    font-size: 30px;
    line-height: 1.15;
    font-weight: 400;
  }

  .latex-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    border-top: 3px solid #000;
    border-bottom: 3px solid #000;
    font-size: 21px;
    line-height: 1.18;
  }

  .latex-table th,
  .latex-table td {
    border: 0 !important;
    padding: 8px 14px 7px 0;
    text-align: left;
    vertical-align: top;
  }

  .latex-table thead th {
    padding-top: 14px;
    padding-bottom: 13px;
    border-bottom: 2px solid #000 !important;
    font-size: 21px;
    font-weight: 700;
  }

  .latex-table .section-row td {
    padding: 8px 22px;
    background: #d9d9d9;
    font-size: 22px;
    font-weight: 700;
  }

  .latex-table .subsection-row td {
    padding: 8px 22px;
    background: #f2f2f2;
    font-size: 22px;
    font-weight: 700;
  }

  .latex-table .section-row.with-rule td {
    border-top: 2px solid #000 !important;
  }

  .latex-table .id-col {
    width: 22%;
    white-space: nowrap;
  }

  .latex-table .definition-col {
    width: 31%;
  }

  .latex-table .examples-col {
    width: 47%;
  }

  .latex-table-caption {
    margin-top: 24px;
    font-size: 16px;
    line-height: 1.45;
    font-family: "Times New Roman", Times, serif;
  }
</style>

<div class="latex-table-block">
  <div class="latex-table-title">Table: Taxonomy of privacy topics (privacy concerns).</div>

  <table class="latex-table">
    <thead>
      <tr>
        <th class="id-col">ID &amp; Topic Name</th>
        <th class="definition-col">Description / Definition</th>
        <th class="examples-col">Examples / Concerns</th>
      </tr>
    </thead>
    <tbody>
      <tr class="section-row">
        <td colspan="3">Privacy Topics -- Data Lifecycle</td>
      </tr>
      <tr class="subsection-row">
        <td colspan="3">A1. Data Collection</td>
      </tr>
      <tr>
        <td>A1.1 Input Content</td>
        <td>Collection and handling of user inputs (including text, voice, images, and files).</td>
        <td>&quot;Does OpenAI store my prompts?&quot;, &quot;Is my voice recorded?&quot;, &quot;What happens to images I upload?&quot;</td>
      </tr>
      <tr>
        <td>A1.2 Behavioral Metadata</td>
        <td>Collection of behavioral data and metadata (usage patterns, device info, IP, timestamps).</td>
        <td>&quot;Do they track when and how often I use it?&quot;, &quot;Is my IP address logged?&quot;</td>
      </tr>
      <tr class="subsection-row">
        <td colspan="3">A2. Data Usage</td>
      </tr>
      <tr>
        <td>A2.1 Service Provision</td>
        <td>Data usage for providing services (response generation, personalization, UX improvement).</td>
        <td>&quot;How is my data used to generate responses?&quot;, &quot;Is my history used to personalize?&quot;</td>
      </tr>
      <tr>
        <td>A2.2 Model Training</td>
        <td>Data usage for AI model training and fundamental improvements (opt-out, scope).</td>
        <td>&quot;Is my data used to train the model?&quot;, &quot;Can I opt out of training?&quot;</td>
      </tr>
      <tr class="subsection-row">
        <td colspan="3">A3. Data Retention &amp; Deletion</td>
      </tr>
      <tr>
        <td>A3.1 Retention Duration</td>
        <td>Data retention periods, storage locations, and lifecycle management.</td>
        <td>&quot;How long do they keep my data?&quot;, &quot;Where is my data stored?&quot;</td>
      </tr>
      <tr>
        <td>A3.2 Deletion Mechanism</td>
        <td>Processes for handling deletion requests, verification, and completeness.</td>
        <td>&quot;Can I delete my conversation history?&quot;, &quot;Is deletion really permanent?&quot;</td>
      </tr>
      <tr class="subsection-row">
        <td colspan="3">A4. Data Sharing</td>
      </tr>
      <tr>
        <td>A4.1 Third Party Sharing</td>
        <td>Data sharing with third parties (advertisers, business partners, government).</td>
        <td>&quot;Do they sell my data to advertisers?&quot;, &quot;Can government access my chats?&quot;</td>
      </tr>
      <tr>
        <td>A4.2 Plugin Extension Access</td>
        <td>Access permissions for plugins, custom GPTs, Actions, or extensions.</td>
        <td>&quot;Can Custom GPTs see my data?&quot;, &quot;What data do plugins access?&quot;</td>
      </tr>
      <tr class="section-row with-rule">
        <td colspan="3">Privacy Topics -- User Rights &amp; Control</td>
      </tr>
      <tr class="subsection-row">
        <td colspan="3">B1. Privacy Awareness &amp; Control</td>
      </tr>
      <tr>
        <td>B1.1 Consent Mechanism</td>
        <td>Mechanisms for obtaining privacy consent (opt-in/out, defaults, scope).</td>
        <td>&quot;Did I consent to data collection?&quot;, &quot;What privacy terms am I agreeing to?&quot;</td>
      </tr>
      <tr>
        <td>B1.2 Granular Control</td>
        <td>Specific privacy control options (Memory toggle, training opt-out, history).</td>
        <td>&quot;Can I turn off memory?&quot;, &quot;How do I opt out of training?&quot;</td>
      </tr>
      <tr>
        <td>B1.3 Transparency Disclosure</td>
        <td>Clarity and disclosure of data processing flows, purposes, and practices.</td>
        <td>&quot;What exactly happens to my data?&quot;, &quot;Why isn't this disclosed clearly?&quot;</td>
      </tr>
      <tr>
        <td>B1.4 Policy Change Notification</td>
        <td>Notification and communication of privacy policy updates (alerts, explanations).</td>
        <td>&quot;Did they change the policy without telling me?&quot;, &quot;How will I know if policy changes?&quot;</td>
      </tr>
      <tr class="section-row with-rule">
        <td colspan="3">Privacy Topics -- AI-Specific Risks</td>
      </tr>
      <tr class="subsection-row">
        <td colspan="3">C1. Model Behavior</td>
      </tr>
      <tr>
        <td>C1.1 Output Risk</td>
        <td>Privacy risks in AI outputs (data leakage, privacy inference, hallucinations).</td>
        <td>&quot;Can ChatGPT leak other users' data?&quot;, &quot;What if AI generates my private info?&quot;</td>
      </tr>
      <tr>
        <td>C1.2 Memory Personalization</td>
        <td>Privacy implications of memory functions (what is remembered, usage, clearance).</td>
        <td>&quot;What does Memory remember about me?&quot;, &quot;Can I see what it remembers?&quot;</td>
      </tr>
      <tr class="subsection-row">
        <td colspan="3">C2. Autonomous &amp; Emerging Applications</td>
      </tr>
      <tr>
        <td>C2.1 Agent Autonomous Actions</td>
        <td>Privacy boundaries for Agent autonomous actions (browsing, code execution).</td>
        <td>&quot;What can the AI agent access?&quot;, &quot;Can it browse my files?&quot;, &quot;What data does web browsing collect?&quot;</td>
      </tr>
      <tr>
        <td>C2.2 Downstream Integration</td>
        <td>Privacy boundaries in downstream integration (API, Embodied AI, IoT, Third-party).</td>
        <td>&quot;What happens to my data when apps use ChatGPT API?&quot;, &quot;Do smart devices share my conversations?&quot;</td>
      </tr>
      <tr class="section-row with-rule">
        <td colspan="3">Privacy Topics -- Compliance &amp; Protection</td>
      </tr>
      <tr class="subsection-row">
        <td colspan="3">D1. Regulatory Compliance</td>
      </tr>
      <tr>
        <td>D1.1 Jurisdiction Law</td>
        <td>Applicable laws, cross-border data transfers, and regional privacy rights.</td>
        <td>&quot;Which laws apply to me?&quot;, &quot;Is my data transferred to other countries?&quot;</td>
      </tr>
      <tr>
        <td>D1.2 Vulnerable Population</td>
        <td>Privacy protection for specific groups (children, elderly, sensitive users).</td>
        <td>&quot;Is it safe for my child?&quot;, &quot;What about COPPA compliance?&quot;</td>
      </tr>
      <tr class="subsection-row">
        <td colspan="3">D2. Security &amp; Incidents</td>
      </tr>
      <tr>
        <td>D2.1 Data Security</td>
        <td>Security measures for privacy data (encryption, access control, secure storage).</td>
        <td>&quot;Is my data encrypted?&quot;, &quot;How do they protect my conversations?&quot;</td>
      </tr>
      <tr>
        <td>D2.2 Breach Notification</td>
        <td>Notification procedures and remedial measures for data privacy breaches.</td>
        <td>&quot;Will they tell me if there's a breach?&quot;, &quot;What happens if my data is leaked?&quot;</td>
      </tr>
    </tbody>
  </table>
</div>

<p class="latex-table-caption">This table operationalizes the privacy concern taxonomy by providing formal definitions, classification criteria, and representative examples for each topic category. This structured specification ensures consistent interpretation of user-expressed concerns across annotators and supports reproducible categorization within the LLM-assisted extraction pipeline.</p>
