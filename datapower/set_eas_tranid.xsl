<?xml version="1.0" encoding="UTF-8"?>
<!--
  set_eas_tranid.xsl

  Resolves the EAS transaction ID for a BCBS ApplicationEligibilityRequest and
  caches it in the DataPower context variable var://context/bcbs/eas_tranid.

  Resolution order:
    1. Use the cached context variable if it was already set earlier in the flow.
    2. Otherwise read IdentificationID from the inbound eligibility request:
         /Envelope/Body/ApplicationEligibilityRequest
           /ExchangeAssignedConsumerIdentification/IdentificationID
       Matched by local-name() so sender-assigned SOAP/ns# prefixes may vary.
    3. If still not found, fall back to the DataPower service transaction id.

  The resolved value is emitted as the template result and stored back into the
  context variable for downstream stages.
-->
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:dp="http://www.datapower.com/extensions"
    extension-element-prefixes="dp">

  <xsl:output method="text" omit-xml-declaration="yes"/>

  <!-- Name of the source element holding the tran ID (kept for reference/logging). -->
  <xsl:variable name="tranIDTag" select="'IdentificationID'"/>

  <xsl:template match="/">
    <xsl:message dp:priority="debug">
      EAS tran ID mapped to tag: <xsl:value-of select="$tranIDTag"/>
    </xsl:message>

    <xsl:variable name="tranID">
      <xsl:choose>
        <xsl:when test="string-length(dp:variable('var://context/bcbs/eas_tranid')) &gt; 0">
          <!-- Already resolved and cached earlier in the flow. -->
          <xsl:value-of select="dp:variable('var://context/bcbs/eas_tranid')"/>
        </xsl:when>
        <xsl:otherwise>
          <!--
            Dynamic tran ID: read IdentificationID from the eligibility request.
            Prefix-agnostic (local-name) so sender-assigned ns#/S prefixes can vary.
          -->
          <xsl:value-of select="
            /*[local-name()='Envelope']
             /*[local-name()='Body']
             /*[local-name()='ApplicationEligibilityRequest']
             /*[local-name()='ExchangeAssignedConsumerIdentification']
             /*[local-name()='IdentificationID'][1]"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:variable>

    <xsl:choose>
      <!-- Was a tran ID found? -->
      <xsl:when test="string-length($tranID) &gt; 0">
        <dp:set-variable name="'var://context/bcbs/eas_tranid'" value="string($tranID)"/>
        <xsl:message dp:priority="debug">
          EAS tran ID found: <xsl:value-of select="$tranID"/>
        </xsl:message>
        <xsl:value-of select="$tranID"/>
      </xsl:when>
      <xsl:otherwise>
        <!-- Fallback: DataPower service transaction id. -->
        <xsl:value-of select="dp:variable('var://service/transaction-id')"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

</xsl:stylesheet>
