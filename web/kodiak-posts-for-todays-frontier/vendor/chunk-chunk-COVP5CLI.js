import{a as e}from"./chunk-chunk-G6O6BLNK.js";var o="mainUVVaryingDeclaration",a=`#ifdef MAINUV{X}
varying vec2 vMainUV{X};
#endif
`;e.IncludesShadersStore[o]||(e.IncludesShadersStore[o]=a);var r="logDepthDeclaration",i=`#ifdef LOGARITHMICDEPTH
uniform float logarithmicDepthConstant;varying float vFragmentDepth;
#endif
`;e.IncludesShadersStore[r]||(e.IncludesShadersStore[r]=i);var t="sceneUboDeclaration",s=`layout(std140,column_major) uniform;uniform Scene {mat4 viewProjection;
#ifdef MULTIVIEW
mat4 viewProjectionR;
#endif 
mat4 view;mat4 projection;vec4 vEyePosition;mat4 inverseProjection;};
`;e.IncludesShadersStore[t]||(e.IncludesShadersStore[t]=s);var n="meshUboDeclaration",c=`#ifdef WEBGL2
uniform mat4 world;uniform float visibility;
#else
layout(std140,column_major) uniform;uniform Mesh
{mat4 world;float visibility;};
#endif
#define WORLD_UBO
`;e.IncludesShadersStore[n]||(e.IncludesShadersStore[n]=c);
