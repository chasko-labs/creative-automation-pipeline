import{a as e}from"./chunk-chunk-G6O6BLNK.js";var o="fogVertexDeclaration",t=`#ifdef FOG
varying vec3 vFogDistance;
#endif
`;e.IncludesShadersStore[o]||(e.IncludesShadersStore[o]=t);var r="fogVertex",n=`#ifdef FOG
vFogDistance=(view*worldPos).xyz;
#endif
`;e.IncludesShadersStore[r]||(e.IncludesShadersStore[r]=n);var d="vertexColorMixing",i=`#if defined(VERTEXCOLOR) || defined(INSTANCESCOLOR) && defined(INSTANCES)
vColor=vec4(1.0);
#ifdef VERTEXCOLOR
#ifdef VERTEXALPHA
vColor*=colorUpdated;
#else
vColor.rgb*=colorUpdated.rgb;
#endif
#endif
#ifdef INSTANCESCOLOR
vColor*=instanceColor;
#endif
#endif
`;e.IncludesShadersStore[d]||(e.IncludesShadersStore[d]=i);
